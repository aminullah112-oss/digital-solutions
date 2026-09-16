"""Domain primitives shared by every layer.

The provenance model is the backbone of this application.  A number on screen
is useless to a technician unless they know where it came from, so a value is
never passed around as a bare float.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Quality(str, enum.Enum):
    """How much the value can be trusted right now."""

    GOOD = "GOOD"
    BAD = "BAD"
    STALE = "STALE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"
    SIMULATED = "SIMULATED"


class DataSource(str, enum.Enum):
    """Where the value came from.  This is the distinction the whole tool
    exists to preserve: a controller reporting an output is ON is not a
    measurement of voltage on a terminal."""

    MEASURED = "MEASURED"           # physical measurement, gateway/DMM
    CONTROLLER = "CONTROLLER"       # reported by the controller over a protocol
    SCHEMATIC = "SCHEMATIC"         # derived from drawing/connectivity
    EXPECTATION = "EXPECTATION"     # engineering expectation, design intent
    INFERENCE = "INFERENCE"         # produced by rules or the AI layer
    SIMULATED = "SIMULATED"         # demo mode
    UNKNOWN = "UNKNOWN"


#: Sources that may never be rendered as if they were a physical measurement.
NON_MEASURED_SOURCES = frozenset(
    {DataSource.CONTROLLER, DataSource.SCHEMATIC, DataSource.EXPECTATION,
     DataSource.INFERENCE, DataSource.SIMULATED, DataSource.UNKNOWN}
)


class ComparisonResult(str, enum.Enum):
    NORMAL = "NORMAL"
    ABNORMAL = "ABNORMAL"
    MARGINAL = "MARGINAL"
    NOT_MEASURED = "NOT_MEASURED"
    NO_EXPECTATION = "NO_EXPECTATION"


class Confidence(str, enum.Enum):
    """Wording used for anything that is not a direct measurement.

    CONFIRMED_BY_MEASUREMENT is the only level that may be reached without a
    hedge, and only when a physical measurement backs it.
    """

    CONFIRMED_BY_MEASUREMENT = "CONFIRMED_BY_MEASUREMENT"
    LIKELY = "LIKELY"
    POSSIBLE = "POSSIBLE"
    UNVERIFIED = "UNVERIFIED"


class NodeType(str, enum.Enum):
    SOURCE = "SOURCE"
    FUSE = "FUSE"
    BREAKER = "BREAKER"
    CONTACTOR = "CONTACTOR"
    RELAY = "RELAY"
    RELAY_COIL = "RELAY_COIL"
    RELAY_CONTACT = "RELAY_CONTACT"
    TERMINAL = "TERMINAL"
    CONNECTOR = "CONNECTOR"
    WIRE = "WIRE"
    SWITCH = "SWITCH"
    SENSOR = "SENSOR"
    TRANSDUCER = "TRANSDUCER"
    CONTROLLER_INPUT = "CONTROLLER_INPUT"
    CONTROLLER_OUTPUT = "CONTROLLER_OUTPUT"
    LOAD = "LOAD"
    GROUND = "GROUND"
    BUS = "BUS"
    TRANSFORMER = "TRANSFORMER"
    PT = "PT"
    CT = "CT"
    UNKNOWN = "UNKNOWN"


class EdgeType(str, enum.Enum):
    CONNECTED_TO = "CONNECTED_TO"
    CONTROLLED_BY = "CONTROLLED_BY"
    POWERED_BY = "POWERED_BY"
    FEEDS = "FEEDS"
    RETURNS_TO = "RETURNS_TO"
    SIGNAL_TO = "SIGNAL_TO"
    PROTECTED_BY = "PROTECTED_BY"


class Severity(str, enum.Enum):
    SHUTDOWN = "SHUTDOWN"
    ALARM = "ALARM"
    WARNING = "WARNING"
    EVENT = "EVENT"
    INFO = "INFO"


class ConnectionState(str, enum.Enum):
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class Protocol(str, enum.Enum):
    MODBUS_TCP = "MODBUS_TCP"
    MODBUS_RTU = "MODBUS_RTU"
    CAN_J1939 = "CAN_J1939"
    OPC_UA = "OPC_UA"
    MQTT = "MQTT"
    SIMULATOR = "SIMULATOR"


class DataType(str, enum.Enum):
    """Register decoding types.  Word order matters on real equipment and is
    an explicit choice, never a guess."""

    INT16 = "INT16"
    UINT16 = "UINT16"
    INT32 = "INT32"
    UINT32 = "UINT32"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"
    BIT = "BIT"
    STRING = "STRING"


class WordOrder(str, enum.Enum):
    BIG = "BIG"        # high word first
    LITTLE = "LITTLE"  # low word first


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    TECHNICIAN = "TECHNICIAN"
    VIEWER = "VIEWER"


#: Mandatory text wherever a medium-voltage circuit is displayed or a
#: measurement task is issued.  Defined once so it cannot drift.
MV_SAFETY_NOTICE = (
    "VERIFY WITH APPROPRIATELY RATED TEST EQUIPMENT AND FOLLOW SITE SAFETY PROCEDURES."
)

#: Threshold at which a circuit is treated as medium voltage for display.
MEDIUM_VOLTAGE_THRESHOLD_V = 1000.0


class ControlNotPermitted(RuntimeError):
    """Raised by any adapter if a write is attempted.

    PowerTrace AI is a read-only diagnostic tool.  It does not start, stop,
    energize, trip or reconfigure anything.
    """


class ProtocolError(RuntimeError):
    """Transport-level failure (connect, timeout, exception response)."""


def value_envelope(
    value: Any,
    unit: str | None,
    quality: Quality,
    source: DataSource,
    *,
    timestamp: datetime | None = None,
    source_detail: str | None = None,
) -> dict[str, Any]:
    """Every value that leaves a service layer is wrapped by this."""
    return {
        "value": value,
        "unit": unit,
        "timestamp": (timestamp or utcnow()).isoformat(),
        "quality": quality.value,
        "source": source.value,
        "source_detail": source_detail,
    }
