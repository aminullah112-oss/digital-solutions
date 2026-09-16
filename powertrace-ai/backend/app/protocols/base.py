"""Protocol adapter interface.

    Controller -> Protocol Adapter -> Normalization -> Application

Adapters return raw decoded parameter readings keyed by `parameter_name`.
They know nothing about generators, and nothing about the UI.

Every adapter is read-only.  `write()` exists on the interface solely so that
the refusal is explicit and testable rather than an accidental omission.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..domain import ControlNotPermitted, DataSource, Quality, utcnow


@dataclass(frozen=True)
class RegisterSpec:
    """Transport-level description of one readable item."""

    parameter_name: str
    address: int
    function_code: int = 3
    data_type: str = "UINT16"
    word_order: str = "BIG"
    length: int = 1
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    bit_position: int | None = None
    normalized_key: str = ""
    description: str = ""


@dataclass
class Reading:
    """One decoded value with full provenance."""

    parameter_name: str
    value: Any
    unit: str
    quality: Quality
    source: DataSource
    timestamp: datetime = field(default_factory=utcnow)
    normalized_key: str = ""
    source_detail: str = ""
    error: str | None = None


@dataclass
class ConnectionInfo:
    ok: bool
    detail: str
    latency_ms: float | None = None
    checked_at: datetime = field(default_factory=utcnow)


class ProtocolAdapter(abc.ABC):
    """Base class for every transport."""

    protocol: str = "UNKNOWN"
    #: Whether values produced by this adapter are physically real.
    produces_simulated_data: bool = False

    def __init__(self, *, descriptor: str = "") -> None:
        self.descriptor = descriptor

    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def close(self) -> None: ...

    @abc.abstractmethod
    def test_connection(self) -> ConnectionInfo: ...

    @abc.abstractmethod
    def read(self, specs: list[RegisterSpec]) -> list[Reading]: ...

    # --- Control path -----------------------------------------------------
    def write(self, *_args: Any, **_kwargs: Any) -> None:
        """Always refuses.

        PowerTrace AI is a diagnostic tool.  It does not start or stop
        engines, open or close breakers, or change controller configuration.
        Any future control capability has to be a separate, explicitly
        authorized module with its own interlocks — not an extension of this
        class.
        """
        raise ControlNotPermitted(
            f"{self.protocol} adapter is read-only: PowerTrace AI issues no control commands."
        )

    def __enter__(self) -> "ProtocolAdapter":
        self.connect()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
