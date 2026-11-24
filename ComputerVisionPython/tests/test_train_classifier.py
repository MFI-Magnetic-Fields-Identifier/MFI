import json
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torchvision")

from mfi_cv.data.train_classifier import TrainingPhotos, _read_dataset, make_demo_dataset


def test_uses_manifest_labels_and_test_images_stay_unread(tmp_path: Path) -> None:
    make_demo_dataset(tmp_path)
    for path in (tmp_path / "test").rglob("*.png"):
        path.unlink()

    labels, samples, digest = _read_dataset(tmp_path)

    assert labels == ["demo-elipse", "demo-retangulo"]
    assert {split: len(items) for split, items in samples.items()} == {"train": 2, "val": 2, "test": 2}
    assert len(digest) == 64
    pixels, label = TrainingPhotos(samples["train"], 32)[0]
    assert pixels.shape == (3, 32, 32)
    assert label == 1


@pytest.mark.parametrize(
    ("field", "expected"), [
        ("session_id", "Vazamento entre partições"),
        ("sha256", "SHA-256 divergente"),
        ("images", "Classes sem imagens em val"),
    ],
)
def test_rejects_invalid_training_dataset(tmp_path: Path, field: str, expected: str) -> None:
    make_demo_dataset(tmp_path)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    images = manifest["images"]
    if field == "session_id":
        images[2][field] = images[0][field]
    elif field == "sha256":
        images[0][field] = "0" * 64
    else:
        images.pop(2)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=expected):
        _read_dataset(tmp_path)
