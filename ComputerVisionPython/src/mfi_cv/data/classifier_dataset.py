import json
from collections import defaultdict
from hashlib import file_digest, sha256
from pathlib import Path

from PIL import Image, ImageDraw


def read_dataset(root: Path, *, verify_splits: tuple[str, ...] = ("train", "val")) -> tuple[list[str], dict[str, list[tuple[Path, int]]], str]:
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    labels = sorted(manifest["classes"])
    if len(labels) < 2:
        raise ValueError("O treinamento requer ao menos duas classes.")
    label_ids = {name: index for index, name in enumerate(labels)}
    samples: dict[str, list[tuple[Path, int]]] = {"train": [], "val": [], "test": []}
    split_by_link: dict[tuple[str, str | int], str] = {}
    counts: dict[str, set[int]] = defaultdict(set)
    for entry in manifest["images"]:
        split, model = entry["split"], entry["model_id"]
        label = label_ids[model]
        if split not in samples:
            raise ValueError(f"Partição inválida: {split}")
        expected = (split, manifest["classes"][model]["directory"])
        relative = Path(entry["path"])
        path = (root / relative).resolve()
        if relative.parts[:2] != expected or len(relative.parts) != 3 or not path.is_relative_to(root):
            raise ValueError(f"Caminho incompatível com o manifesto: {relative}")
        for key in ("unit_id", "session_id", "sha256", "group_id"):
            link = (key, entry[key])
            if split_by_link.setdefault(link, split) != split:
                raise ValueError(f"Vazamento entre partições no campo {key}: {entry[key]}")
        if split in verify_splits:
            with path.open("rb") as image_file:
                digest = file_digest(image_file, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"SHA-256 divergente no dataset: {relative}")
        samples[split].append((path, label))
        counts[split].add(label)
    for split in ("train", "val"):
        missing = [name for name, label in label_ids.items() if label not in counts[split]]
        if missing:
            raise ValueError(f"Classes sem imagens em {split}: {', '.join(missing)}.")
    return labels, samples, sha256(manifest_bytes).hexdigest()


def make_demo_dataset(root: Path) -> None:
    """Cria figuras sintéticas independentes para testar a execução do treino."""
    classes = {"demo-retangulo": {"directory": "retangulo"}, "demo-elipse": {"directory": "elipse"}}
    images = []
    for split_index, split in enumerate(("train", "val", "test")):
        for label_index, (label, info) in enumerate(classes.items()):
            relative = Path(split, info["directory"], "demo.png")
            path = root / relative
            path.parent.mkdir(parents=True)
            photo = Image.new("RGB", (120, 80), (30 + 20 * split_index, 40, 50))
            draw = ImageDraw.Draw(photo)
            shape = draw.rectangle if label_index == 0 else draw.ellipse
            shape((18 + split_index * 4, 16, 100, 65), fill="#dfd4ab")
            photo.save(path)
            example_id = f"{split}-{label}"
            images.append({
                "split": split, "model_id": label, "path": relative.as_posix(),
                "unit_id": example_id, "session_id": example_id, "group_id": example_id,
                "sha256": sha256(path.read_bytes()).hexdigest(),
            })
    (root / "manifest.json").write_text(json.dumps({"classes": classes, "images": images}), encoding="utf-8")
