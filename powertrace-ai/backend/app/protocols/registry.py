"""Builds the right adapter for a controller."""
from __future__ import annotations

from ..config import settings
from ..domain import Protocol, ProtocolError
from ..models import Controller
from .base import ProtocolAdapter
from .future import CanJ1939Adapter, ModbusRtuAdapter, MqttAdapter, OpcUaAdapter
from .modbus_tcp import ModbusTcpAdapter
from .simulator import SimulatorAdapter

_FUTURE = {
    Protocol.MODBUS_RTU: ModbusRtuAdapter,
    Protocol.CAN_J1939: CanJ1939Adapter,
    Protocol.OPC_UA: OpcUaAdapter,
    Protocol.MQTT: MqttAdapter,
}


def build_adapter(controller: Controller) -> ProtocolAdapter:
    cfg = controller.protocol_config
    if cfg is None:
        raise ProtocolError(f"controller {controller.name!r} has no protocol configuration")

    protocol = Protocol(cfg.protocol)

    if controller.is_simulated or protocol is Protocol.SIMULATOR:
        return SimulatorAdapter(
            key=f"controller-{controller.id}",
            descriptor=f"simulator://{controller.name}",
            **{k: v for k, v in (cfg.options or {}).items() if k.startswith("nominal_")
               or k in ("rated_kw", "control_voltage_v")},
        )

    if protocol is Protocol.MODBUS_TCP:
        if not cfg.host:
            raise ProtocolError(f"controller {controller.name!r} has no host configured")
        return ModbusTcpAdapter(
            host=cfg.host,
            port=cfg.port or 502,
            unit_id=cfg.unit_id,
            timeout_s=cfg.timeout_s or settings.modbus_timeout_s,
            retries=cfg.retries if cfg.retries is not None else settings.modbus_retries,
            descriptor=f"modbus-tcp://{cfg.host}:{cfg.port or 502}/{cfg.unit_id}",
        )

    adapter_cls = _FUTURE.get(protocol)
    if adapter_cls is None:
        raise ProtocolError(f"unsupported protocol {protocol}")
    return adapter_cls(**(cfg.options or {}))
