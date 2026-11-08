"""Project metadata and the flattened, validated configuration."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .parameter import Parameter, Status


class ConfigError(Exception):
    """The configuration file is malformed or inconsistent. It is not a design finding."""


class ReleaseState(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    INTERNAL_TEST = "INTERNAL_TEST"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    APPROVED_FOR_EDUCATIONAL_DISTRIBUTION = "APPROVED_FOR_EDUCATIONAL_DISTRIBUTION"
    RELEASE_BLOCKED = "RELEASE_BLOCKED"


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    name: str
    product_code: str
    edition: str
    revision: str
    release_state: ReleaseState
    current_stage: int = 1


class Category(str, Enum):
    IT_CRITICAL = "it_critical"
    MECHANICAL_COOLING = "mechanical_cooling"
    LIGHTING_SMALL_POWER = "lighting_small_power"
    AUXILIARY = "auxiliary"


class LoadItem(BaseModel):
    """One line of the load schedule, with the same provenance as a parameter."""

    model_config = ConfigDict(extra="forbid")
    id: str
    category: Category
    description: str
    quantity: float
    unit_rating_kw: float | None = None
    unit_rating_ref: str | None = None
    rating_from: str | None = None  # set by the loader: the design-basis parameter the rating was read from
    power_factor: float
    demand_factor: float
    path_a_fraction: float
    on_generator: bool = True  # whether the item is supplied by the generators during a utility outage
    status: Status
    source: str
    revision: str
    notes: str = ""

    @field_validator("quantity")
    @classmethod
    def _qty(cls, v):
        if not v > 0:
            raise ValueError("quantity must be above zero")
        return v

    @field_validator("power_factor", "demand_factor")
    @classmethod
    def _frac(cls, v):
        if not (0 < v <= 1):
            raise ValueError("must be above 0 and at most 1")
        return v

    @field_validator("path_a_fraction")
    @classmethod
    def _path(cls, v):
        if not (0 <= v <= 1):
            raise ValueError("path_a_fraction must be between 0 and 1")
        return v

    @model_validator(mode="after")
    def _rating(self):
        if (self.unit_rating_kw is None) == (self.unit_rating_ref is None):
            raise ValueError(f"{self.id}: give exactly one of unit_rating_kw or unit_rating_ref")
        if self.unit_rating_kw is not None and not self.unit_rating_kw > 0:
            raise ValueError(f"{self.id}: unit_rating_kw must be above zero")
        for f in ("description", "source", "revision"):
            if not getattr(self, f).strip():
                raise ValueError(f"{self.id}: '{f}' must not be empty")
        return self

    @property
    def missing(self) -> bool:
        return self.unit_rating_kw is None


class DesignException(BaseModel):
    """An accepted design-target exception. It annotates a check; it never changes the check's status."""

    model_config = ConfigDict(extra="forbid")
    id: str
    check_id: str
    title: str
    accepted_ceiling_pct: float
    basis: str
    accepted_by: str
    accepted_date: str
    status: str
    conditions: list[str]
    verification_action: str
    verified_by: str | None = None
    verification_date: str | None = None

    @field_validator("accepted_date", mode="before")
    @classmethod
    def _date(cls, v):
        return str(v)


class ProjectConfig(BaseModel):
    schema_version: int
    project: ProjectMeta
    parameters: dict[str, Parameter]
    load_items: list[LoadItem] = []
    exceptions: list[DesignException] = []
    distribution: dict = {}
    base_dir: str = "."

    def get(self, pid: str) -> Parameter:
        try:
            return self.parameters[pid]
        except KeyError:
            raise ConfigError(f"Unknown parameter '{pid}'") from None

    def value(self, pid: str):
        """The parameter's value, or None if it has not been supplied."""
        return self.get(pid).value

    def optional_value(self, pid: str):
        """Like value(), but None when the parameter does not exist (an older revision may lack a newer parameter)."""
        p = self.parameters.get(pid)
        return None if p is None else p.value

    def missing(self) -> list[Parameter]:
        """Required inputs that are missing and already needed at the current stage."""
        return [p for p in self.parameters.values() if p.required and p.missing and p.needed_from_stage <= self.project.current_stage]

    def deferred(self) -> list[Parameter]:
        """Required inputs that are missing but not needed until a later stage."""
        return [p for p in self.parameters.values() if p.required and p.missing and p.needed_from_stage > self.project.current_stage]
