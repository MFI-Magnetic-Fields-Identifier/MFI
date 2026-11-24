from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser um texto não vazio.")


class ValidationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class MotorModel:
    """Modelo comercial e especificações conhecidas da documentação de origem."""

    model_id: str
    manufacturer: str
    product_line: str
    commercial_model: str
    source_reference: str
    technical_specs: Mapping[str, str | int | float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.model_id, "model_id")
        _require_text(self.manufacturer, "manufacturer")
        _require_text(self.product_line, "product_line")
        _require_text(self.commercial_model, "commercial_model")
        _require_text(self.source_reference, "source_reference")


@dataclass(frozen=True)
class MotorUnit:
    """Exemplar físico com identificador interno próprio."""

    unit_id: str
    model: MotorModel

    def __post_init__(self) -> None:
        _require_text(self.unit_id, "unit_id")
        if not isinstance(self.model, MotorModel):
            raise ValueError("model deve ser um MotorModel.")


@dataclass(frozen=True)
class CaptureSession:
    """Agrupa fotografias coletadas na mesma sessão."""

    session_id: str

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")


@dataclass(frozen=True)
class MotorImage:
    """Registro de uma fotografia associada a um exemplar e a uma sessão."""

    image_id: str
    path: Path
    unit: MotorUnit
    session: CaptureSession
    origin: str
    registered_at: datetime
    capture_angle_deg: float | None = None
    validation_status: ValidationStatus = ValidationStatus.PENDING

    def __post_init__(self) -> None:
        _require_text(self.image_id, "image_id")
        _require_text(self.origin, "origin")
        if not isinstance(self.path, Path) or not self.path.name:
            raise ValueError("path deve identificar um arquivo.")
        if not isinstance(self.unit, MotorUnit):
            raise ValueError("unit deve ser um MotorUnit.")
        if not isinstance(self.session, CaptureSession):
            raise ValueError("session deve ser uma CaptureSession.")
        if not isinstance(self.registered_at, datetime) or self.registered_at.utcoffset() is None:
            raise ValueError("registered_at deve ser uma data e hora com fuso horário.")
        angle = self.capture_angle_deg
        if angle is not None and (
            type(angle) not in (int, float) or not 0 <= angle < 360
        ):
            raise ValueError("capture_angle_deg deve estar no intervalo [0, 360).")
        if not isinstance(self.validation_status, ValidationStatus):
            raise ValueError("validation_status deve ser um ValidationStatus.")

    @property
    def model_id(self) -> str:
        return self.unit.model.model_id
