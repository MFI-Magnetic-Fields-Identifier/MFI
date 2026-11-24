import argparse
import json
from collections import defaultdict
from hashlib import file_digest, sha256
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

import torch
import torchvision
from PIL import Image, ImageDraw
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from .photo_files import open_photo
from .preprocessing import DEFAULT_SIZE, PADDING_COLOR, normalize_rgb, prepare_image

WEIGHTS = MobileNet_V3_Small_Weights.IMAGENET1K_V1


def _read_dataset(root: Path) -> tuple[list[str], dict[str, list[tuple[Path, int]]], str]:
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
        if split != "test":
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


class TrainingPhotos(Dataset[tuple[Tensor, int]]):
    def __init__(self, samples: list[tuple[Path, int]], size: int) -> None:
        self.samples = samples
        self.size = size
        preset = WEIGHTS.transforms()
        self.mean = torch.tensor(preset.mean).view(3, 1, 1)
        self.std = torch.tensor(preset.std).view(3, 1, 1)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Tensor, int]:
        path, label = self.samples[index]
        with open_photo(path) as original:
            rgb = prepare_image(original, size=self.size)
        pixels = torch.frombuffer(normalize_rgb(rgb), dtype=torch.float32).view(3, self.size, self.size)
        return (pixels - self.mean) / self.std, label


def _epoch(
    model: nn.Module, loader: DataLoader, device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> tuple[float, float]:
    # A base congelada permanece em avaliação para preservar as estatísticas de BatchNorm.
    loss_sum = 0.0
    correct = 0
    total = 0
    with torch.set_grad_enabled(optimizer is not None):
        for pixels, labels in loader:
            pixels, labels = pixels.to(device), labels.to(device)
            if optimizer is not None:
                optimizer.zero_grad()
            logits = model(pixels)
            loss = nn.functional.cross_entropy(logits, labels)
            if optimizer is not None:
                loss.backward()
                optimizer.step()
            total += labels.numel()
            loss_sum += loss.item() * labels.numel()
            correct += (logits.argmax(dim=1) == labels).sum().item()
    return loss_sum / total, correct / total


def train(
    root: Path, output: Path, *, epochs: int, batch_size: int, size: int,
    seed: int, requested_device: str, demo: bool = False,
) -> None:
    if min(epochs, batch_size, size) < 1 or not 0 <= seed < 2**63:
        raise ValueError("Use épocas, lote e tamanho positivos e seed entre 0 e 2**63 - 1.")
    if output.exists():
        raise ValueError(f"A pasta de saída já existe: {output}")
    has_cuda = torch.cuda.is_available()
    if requested_device == "cuda" and not has_cuda:
        raise ValueError("CUDA indisponível nesta instalação do PyTorch.")
    if requested_device == "auto":
        requested_device = "cuda" if has_cuda else "cpu"
    device = torch.device(requested_device)
    labels, samples, manifest_hash = _read_dataset(root.resolve())
    torch.manual_seed(seed)
    datasets = {split: TrainingPhotos(samples[split], size) for split in ("train", "val")}
    train_loader = DataLoader(
        datasets["train"], batch_size=batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    val_loader = DataLoader(datasets["val"], batch_size=batch_size)
    model = mobilenet_v3_small(weights=WEIGHTS)
    model.requires_grad_(False)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(labels))
    model.to(device).eval()
    learning_rate = 0.001
    optimizer = torch.optim.Adam(model.classifier[-1].parameters(), lr=learning_rate)
    preset = WEIGHTS.transforms()
    config = {
        "demo": demo, "architecture": "mobilenet_v3_small", "initial_weights": WEIGHTS.name,
        "epochs": epochs, "batch_size": batch_size, "learning_rate": learning_rate,
        "seed": seed, "device": str(device), "cuda_available": has_cuda, "class_ids": labels,
        "torch_version": str(torch.__version__), "torchvision_version": str(torchvision.__version__),
        "manifest_sha256": manifest_hash, "image_counts": {key: len(value) for key, value in samples.items()},
        "preprocessing": {
            "size": size, "exif_orientation": True, "resize": "letterbox_lanczos",
            "padding_rgb": list(PADDING_COLOR), "scale": 255, "mean": preset.mean, "std": preset.std,
        },
    }
    print(f"Modo {'demonstração sintética' if demo else 'catálogo'} | dispositivo {device}", flush=True)
    output.mkdir(parents=True)
    (output / "run.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    best_loss = float("inf")
    with (output / "metrics.jsonl").open("w", encoding="utf-8") as log:
        for epoch in range(1, epochs + 1):
            train_loss, train_accuracy = _epoch(model, train_loader, device, optimizer)
            val_loss, val_accuracy = _epoch(model, val_loader, device)
            if not isfinite(train_loss) or not isfinite(val_loss):
                raise ValueError(f"Perda não finita na época {epoch}.")
            metrics = {
                "epoch": epoch, "train_loss": train_loss, "train_accuracy": train_accuracy,
                "val_loss": val_loss, "val_accuracy": val_accuracy,
            }
            print(json.dumps(metrics), flush=True)
            log.write(json.dumps(metrics) + "\n")
            log.flush()
            if val_loss < best_loss:
                best_loss = val_loss
                temporary_weights = output / "best.pt.tmp"
                torch.save({"state_dict": model.state_dict(), "config": config, "metrics": metrics}, temporary_weights)
                temporary_weights.replace(output / "best.pt")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina o classificador MobileNetV3 Small do MFI.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    options = dict(
        epochs=args.epochs, batch_size=args.batch_size, size=args.size, seed=args.seed,
        requested_device=args.device, demo=args.demo,
    )
    try:
        if args.demo:
            with TemporaryDirectory(prefix="mfi-training-demo-") as demo_dir:
                root = Path(demo_dir)
                make_demo_dataset(root)
                train(root, args.output, **options)
        else:
            train(args.dataset, args.output, **options)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        parser.exit(1, f"Erro no treinamento: {error}\n")


if __name__ == "__main__":
    main()
