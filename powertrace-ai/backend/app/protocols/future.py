"""Interfaces for transports that are specified but not implemented.

These exist so the abstraction is real rather than aspirational: the registry
can resolve them, the UI can list them, and attempting to use one produces a
clear, honest error instead of a stack trace or, worse, fabricated data.
"""
from __future__ import annotations

from ..domain import ProtocolError
from .base import ConnectionInfo, ProtocolAdapter, Reading, RegisterSpec


class _NotImplementedAdapter(ProtocolAdapter):
    note = ""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(descriptor=f"{self.protocol}(unimplemented)")
        self.kwargs = kwargs

    def _fail(self) -> None:
        raise ProtocolError(
            f"{self.protocol} is defined in the protocol layer but not implemented. {self.note}"
        )

    def connect(self) -> None:
        self._fail()

    def close(self) -> None:
        return None

    def test_connection(self) -> ConnectionInfo:
        return ConnectionInfo(
            ok=False,
            detail=f"{self.protocol} adapter not implemented. {self.note}",
        )

    def read(self, specs: list[RegisterSpec]) -> list[Reading]:
        self._fail()
        return []


class ModbusRtuAdapter(_NotImplementedAdapter):
    protocol = "MODBUS_RTU"
    note = "Requires a serial port binding and per-site line parameters."


class CanJ1939Adapter(_NotImplementedAdapter):
    protocol = "CAN_J1939"
    note = "Requires a CAN interface and a PGN/SPN decode table."


class OpcUaAdapter(_NotImplementedAdapter):
    protocol = "OPC_UA"
    note = "Requires an endpoint URL, security policy and node ID mapping."


class MqttAdapter(_NotImplementedAdapter):
    protocol = "MQTT"
    note = "Requires broker details and a topic/payload schema."
