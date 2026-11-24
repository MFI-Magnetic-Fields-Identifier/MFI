from datetime import UTC, datetime
from hashlib import file_digest
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from uuid import uuid4
from warnings import catch_warnings, simplefilter

from PIL import Image
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .models import MotorImage
from .repository import MotorRepository

_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class DuplicateImageError(ValueError):
    """Os mesmos bytes já estão associados a um registro de imagem."""

    def __init__(self, image_id: str) -> None:
        self.image_id = image_id
        super().__init__(f"Arquivo duplicado da imagem {image_id}.")


def _photo_extension(path: Path) -> str:
    try:
        with catch_warnings():
            simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path, formats=tuple(_EXTENSIONS)) as photo:
                image_format = photo.format
                if image_format not in _EXTENSIONS or getattr(photo, "is_animated", False):
                    raise ValueError("Esperada uma imagem estática JPEG, PNG ou WebP.")
                photo.verify()
            # verify() verifica a estrutura. Reabrir permite testar a decodificação.
            with Image.open(path, formats=(image_format,)) as photo:
                photo.load()
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Imagem inválida ou fora dos formatos JPEG, PNG e WebP.") from exc
    return _EXTENSIONS[image_format]


def import_photo(
    engine: Engine,
    source: Path,
    *,
    unit_id: str,
    session_id: str,
    origin: str,
    storage_root: Path = Path("dataset/raw"),
    capture_angle_deg: float | None = None,
) -> MotorImage:
    """Registra uma fotografia em sua própria transação e conserva os bytes originais."""
    storage_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".import-", dir=storage_root) as staging:
        staged_file = Path(staging) / "photo"
        copyfile(source, staged_file)
        extension = _photo_extension(staged_file)
        with staged_file.open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()

        relative_path = Path(digest[:2]) / f"{digest}{extension}"
        destination = storage_root / relative_path
        try:
            with engine.begin() as connection:
                repository = MotorRepository(connection)
                unit = repository.get_unit(unit_id)
                if unit is None:
                    raise ValueError(f"Exemplar não cadastrado: {unit_id}")
                session = repository.get_session(session_id)
                if session is None:
                    raise ValueError(f"Sessão não cadastrada: {session_id}")
                image = MotorImage(
                    image_id=uuid4().hex,
                    path=relative_path,
                    unit=unit,
                    session=session,
                    origin=origin,
                    registered_at=datetime.now(UTC),
                    capture_angle_deg=capture_angle_deg,
                    sha256=digest,
                    original_filename=source.name,
                )
                repository.add_image(image)
                destination.parent.mkdir(exist_ok=True)
                staged_file.replace(destination)
        except IntegrityError as exc:
            with engine.connect() as connection:
                existing_id = MotorRepository(connection).find_image_id_by_sha256(digest)
            if existing_id is not None:
                raise DuplicateImageError(existing_id) from exc
            raise
    return image
