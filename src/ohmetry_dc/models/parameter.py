"""A single configuration parameter with its provenance."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class Status(str, Enum):
    USER_INPUT = "USER_INPUT"
    ASSUMPTION = "ASSUMPTION"
    MANUFACTURER_DATA = "MANUFACTURER_DATA"
    REFERENCE = "REFERENCE"


class Parameter(BaseModel):
    """Every input carries a name, value, unit, description, source, status and revision.

    A value of None means the input has not been supplied. It is reported as missing and is never replaced by a default.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    name: str
    value: float | int | str | bool | None = None
    value_ref: str | None = None
    unit: str
    description: str
    source: str
    status: Status
    revision: str
    notes: str = ""
    required: bool = True
    needed_from_stage: int = 1  # the development stage that first needs this input; earlier stages do not report it as missing
    original_value: float | int | str | bool | None = None      # the master design-basis value, kept when a supplied value overrides it
    original_source: str | None = None
    datasheet_revision: str | None = None
    override_date: str | None = None
    requires_manufacturer_verification: bool = False  # a placeholder or assumed value that a manufacturer data sheet must confirm; it must have a manufacturer-data register entry

    @model_validator(mode="after")
    def _check(self) -> "Parameter":
        for field in ("name", "unit", "description", "source", "revision"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{self.id or self.name}: '{field}' must not be empty")
        if self.value is not None and self.value_ref is not None:
            raise ValueError(f"{self.id or self.name}: give either 'value' or 'value_ref', not both")
        if self.status in (Status.ASSUMPTION, Status.REFERENCE) and self.value is None and self.value_ref is None:
            raise ValueError(f"{self.id or self.name}: an {self.status.value} must have a value (use USER_INPUT or MANUFACTURER_DATA for data that is not yet supplied)")
        return self

    @property
    def missing(self) -> bool:
        return self.value is None
