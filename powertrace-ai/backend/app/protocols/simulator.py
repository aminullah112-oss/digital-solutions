"""Simulated controller for DEMO MODE.

Every value produced here carries Quality.SIMULATED and DataSource.SIMULATED.
Those tags are set at the point of production and are never rewritten
downstream, so a simulated value cannot reach the UI looking like a real one.

The simulation is deliberately simple physics — enough to exercise the
diagnostic engine and the UI, not a genset model.  It is not used to validate
anything about real equipment.
"""
from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..domain import DataSource, Quality, utcnow
from .base import ConnectionInfo, ProtocolAdapter, Reading, RegisterSpec

#: Faults the demo can inject.  Each one produces a self-consistent set of
#: controller values, alarms and (where relevant) gateway measurements.
FAULT_MODES = [
    "NONE",
    "LOW_VOLTAGE",
    "HIGH_VOLTAGE",
    "OVERCURRENT",
    "REVERSE_REACTIVE_POWER",
    "FREQUENCY_ABNORMAL",
    "BREAKER_FAIL_TO_CLOSE",
    "BREAKER_FAIL_TO_OPEN",
    "SENSOR_FAILURE",
    "COMMUNICATION_LOSS",
    "CONTROL_VOLTAGE_LOSS",
]


@dataclass
class SimState:
    """Mutable state of one simulated genset."""

    nominal_voltage_v: float = 4160.0
    nominal_frequency_hz: float = 60.0
    nominal_rpm: float = 1800.0
    rated_kw: float = 2000.0
    control_voltage_v: float = 24.0

    running: bool = True
    breaker_closed: bool = True
    close_command: bool = False
    fault_mode: str = "NONE"
    started_at: float = field(default_factory=time.time)
    engine_hours: float = 4821.3
    seed: int = 1
    _rng: random.Random = field(default_factory=lambda: random.Random(1))

    def noise(self, scale: float) -> float:
        return self._rng.uniform(-scale, scale)


class SimulatorAdapter(ProtocolAdapter):
    """In-process simulated controller.

    Shares one `SimState` per controller id so that the API can inject faults
    and the poller immediately sees the effect.
    """

    protocol = "SIMULATOR"
    produces_simulated_data = True

    _states: dict[str, SimState] = {}
    _lock = threading.Lock()

    def __init__(self, key: str, *, descriptor: str = "", **overrides: Any) -> None:
        super().__init__(descriptor=descriptor or f"simulator://{key}")
        self.key = key
        with self._lock:
            if key not in self._states:
                state = SimState()
                for name, value in overrides.items():
                    if hasattr(state, name):
                        setattr(state, name, value)
                state._rng = random.Random(hash(key) & 0xFFFF)
                self._states[key] = state
        self.state = self._states[key]

    # --- demo control -----------------------------------------------------
    @classmethod
    def state_for(cls, key: str) -> SimState | None:
        return cls._states.get(key)

    @classmethod
    def all_states(cls) -> dict[str, SimState]:
        return dict(cls._states)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._states.clear()

    def set_fault(self, mode: str) -> None:
        if mode not in FAULT_MODES:
            raise ValueError(f"unknown fault mode {mode!r}")
        self.state.fault_mode = mode
        # The injected fault drives the consequential state so that the
        # controller picture and the circuit picture agree.
        if mode == "BREAKER_FAIL_TO_CLOSE":
            self.state.breaker_closed = False
            self.state.close_command = True
        elif mode == "BREAKER_FAIL_TO_OPEN":
            self.state.breaker_closed = True
            self.state.close_command = False
        elif mode == "CONTROL_VOLTAGE_LOSS":
            self.state.breaker_closed = False
            self.state.close_command = True
        elif mode == "NONE":
            self.state.breaker_closed = True
            self.state.close_command = False

    # --- lifecycle --------------------------------------------------------
    def connect(self) -> None:
        if self.state.fault_mode == "COMMUNICATION_LOSS":
            from ..domain import ProtocolError

            raise ProtocolError("SIMULATED communication loss (demo fault injection)")

    def close(self) -> None:
        return None

    def test_connection(self) -> ConnectionInfo:
        if self.state.fault_mode == "COMMUNICATION_LOSS":
            return ConnectionInfo(ok=False, detail="SIMULATED communication loss")
        return ConnectionInfo(
            ok=True, detail="Simulated controller — DEMO MODE, no physical device", latency_ms=0.4
        )

    # --- values -----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Compute the full simulated parameter set."""
        s = self.state
        t = time.time()
        if s.fault_mode == "COMMUNICATION_LOSS":
            return {}

        running = s.running and s.fault_mode != "SENSOR_FAILURE" or s.running
        v_mult = {"LOW_VOLTAGE": 0.86, "HIGH_VOLTAGE": 1.13}.get(s.fault_mode, 1.0)
        f_offset = {"FREQUENCY_ABNORMAL": -2.4}.get(s.fault_mode, 0.0)

        vll = s.nominal_voltage_v * v_mult + s.noise(4.0) if running else 0.0
        freq = (s.nominal_frequency_hz + f_offset + s.noise(0.05)) if running else 0.0
        rpm = freq / s.nominal_frequency_hz * s.nominal_rpm if running else 0.0

        base_kw = s.rated_kw * 0.62 if (running and s.breaker_closed) else 0.0
        if base_kw > 0.0:
            kw = base_kw * (1.0 + 0.02 * math.sin(t / 7.0)) + s.noise(6.0)
            kvar = base_kw * 0.30
            if s.fault_mode == "REVERSE_REACTIVE_POWER":
                kvar = -abs(base_kw * 0.45)
        else:
            # Breaker open: the machine is not exporting anything.  Zero, not
            # noise around zero — a technician reading 4 kW on an open breaker
            # would rightly distrust the whole screen.
            kw = kvar = 0.0
        kva = math.hypot(kw, kvar)
        pf = (kw / kva) if kva > 1e-6 else 0.0

        current = (kva * 1000.0) / (math.sqrt(3) * vll) if vll > 1 else 0.0
        if s.fault_mode == "OVERCURRENT":
            current *= 1.9

        oil_pressure = 58.0 + s.noise(1.2) if running else 0.0
        coolant = 82.0 + s.noise(0.8) if running else 24.0
        if s.fault_mode == "SENSOR_FAILURE":
            oil_pressure = 0.0  # open-circuit sender reads zero on many controllers

        ctrl_v = 0.4 if s.fault_mode == "CONTROL_VOLTAGE_LOSS" else s.control_voltage_v + s.noise(0.2)

        # Discrete I/O.  DO-07 is the breaker close command in the demo panel.
        do07 = bool(s.close_command)
        breaker_fb = bool(s.breaker_closed)

        return {
            "voltage_L1_L2": (vll, "V"),
            "voltage_L2_L3": (vll + s.noise(6.0), "V"),
            "voltage_L3_L1": (vll + s.noise(6.0), "V"),
            "voltage_L1_N": (vll / math.sqrt(3) if vll else 0.0, "V"),
            "current_L1": (current, "A"),
            "current_L2": (current + s.noise(3.0), "A"),
            "current_L3": (current + s.noise(3.0), "A"),
            "frequency": (freq, "Hz"),
            "rpm": (rpm, "rpm"),
            "kw": (kw, "kW"),
            "kvar": (kvar, "kVAr"),
            "kva": (kva, "kVA"),
            "power_factor": (pf, ""),
            "breaker_status": (breaker_fb, ""),
            "engine_status": ("RUNNING" if running else "STOPPED", ""),
            "generator_status": (
                "ONLINE" if (running and s.breaker_closed) else "AVAILABLE" if running else "OFF",
                "",
            ),
            "oil_pressure": (oil_pressure, "psi"),
            "coolant_temperature": (coolant, "degC"),
            "fuel_level": (74.0 + s.noise(0.4), "%"),
            "battery_voltage": (ctrl_v, "V"),
            "engine_speed": (rpm, "rpm"),
            "engine_hours": (s.engine_hours + (t - s.started_at) / 3600.0, "h"),
            "control_voltage": (ctrl_v, "V"),
            "DO_07": (do07, ""),
            "DO_08": (False, ""),
            "DI_11": (breaker_fb, ""),
            "DI_12": (bool(running), ""),
            "breaker_close_command": (do07, ""),
            "breaker_closed_feedback": (breaker_fb, ""),
        }

    def read(self, specs: list[RegisterSpec]) -> list[Reading]:
        values = self.snapshot()
        now = utcnow()
        readings: list[Reading] = []
        for spec in specs:
            if spec.parameter_name in values:
                raw, unit = values[spec.parameter_name]
                readings.append(
                    Reading(
                        parameter_name=spec.parameter_name,
                        value=round(raw, 3) if isinstance(raw, float) else raw,
                        unit=spec.unit or unit,
                        quality=Quality.SIMULATED,
                        source=DataSource.SIMULATED,
                        normalized_key=spec.normalized_key or spec.parameter_name,
                        source_detail=f"{self.descriptor} (DEMO MODE)",
                        timestamp=now,
                    )
                )
            else:
                readings.append(
                    Reading(
                        parameter_name=spec.parameter_name,
                        value=None,
                        unit=spec.unit,
                        quality=Quality.UNKNOWN,
                        source=DataSource.SIMULATED,
                        normalized_key=spec.normalized_key,
                        source_detail=self.descriptor,
                        error="parameter not modelled by the simulator",
                    )
                )
        return readings

    def simulated_alarms(self) -> list[dict[str, Any]]:
        """Alarms the simulated controller is reporting.

        Codes and texts here are explicitly marked as simulator-generated and
        are not taken from any manufacturer's alarm list.
        """
        s = self.state
        table = {
            "LOW_VOLTAGE": ("SIM-UV1", "SIMULATED: generator undervoltage", "ALARM"),
            "HIGH_VOLTAGE": ("SIM-OV1", "SIMULATED: generator overvoltage", "ALARM"),
            "OVERCURRENT": ("SIM-OC1", "SIMULATED: generator overcurrent", "ALARM"),
            "REVERSE_REACTIVE_POWER": (
                "SIM-RKV", "SIMULATED: reverse reactive power", "ALARM",
            ),
            "FREQUENCY_ABNORMAL": ("SIM-UF1", "SIMULATED: underfrequency", "ALARM"),
            "BREAKER_FAIL_TO_CLOSE": (
                "SIM-BFC", "SIMULATED: generator breaker failed to close", "SHUTDOWN",
            ),
            "BREAKER_FAIL_TO_OPEN": (
                "SIM-BFO", "SIMULATED: generator breaker failed to open", "SHUTDOWN",
            ),
            "SENSOR_FAILURE": (
                "SIM-SNS", "SIMULATED: engine oil pressure sensor signal lost", "WARNING",
            ),
            "CONTROL_VOLTAGE_LOSS": (
                "SIM-CVL", "SIMULATED: control voltage low", "ALARM",
            ),
            "COMMUNICATION_LOSS": ("SIM-COM", "SIMULATED: communication loss", "ALARM"),
        }
        entry = table.get(s.fault_mode)
        if not entry:
            return []
        code, text, severity = entry
        return [{"code": code, "description": text, "severity": severity}]
