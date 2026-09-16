"""Modbus TCP adapter.

Reads only.  Function codes 1 (coils), 2 (discrete inputs), 3 (holding) and
4 (input registers) are supported; nothing else is implemented, so there is no
code path that can write a coil or a register.

pymodbus is imported lazily so the rest of the application — demo mode,
schematic work, report generation — runs on a machine where it is not
installed.
"""
from __future__ import annotations

import struct
import time
from typing import Any

from ..domain import DataSource, ProtocolError, Quality, utcnow
from .base import ConnectionInfo, ProtocolAdapter, Reading, RegisterSpec

READ_FUNCTION_CODES = {1, 2, 3, 4}
_BIT_FUNCTION_CODES = {1, 2}


def _words_to_bytes(words: list[int], word_order: str) -> bytes:
    ordered = words if word_order.upper() == "BIG" else list(reversed(words))
    return b"".join(struct.pack(">H", w & 0xFFFF) for w in ordered)


def decode_words(words: list[int], spec: RegisterSpec) -> Any:
    """Decode raw 16-bit words per the register definition.

    Word order is taken from the definition, never guessed: getting it wrong
    silently produces plausible nonsense, which is the worst possible failure
    for a diagnostic tool.
    """
    dt = spec.data_type.upper()
    if dt == "BIT":
        if spec.bit_position is None:
            raise ValueError(f"{spec.parameter_name}: BIT type requires bit_position")
        return bool((words[0] >> spec.bit_position) & 1)
    if dt == "UINT16":
        return words[0] & 0xFFFF
    if dt == "INT16":
        return struct.unpack(">h", struct.pack(">H", words[0] & 0xFFFF))[0]
    if dt == "UINT32":
        return struct.unpack(">I", _words_to_bytes(words[:2], spec.word_order))[0]
    if dt == "INT32":
        return struct.unpack(">i", _words_to_bytes(words[:2], spec.word_order))[0]
    if dt == "FLOAT32":
        return struct.unpack(">f", _words_to_bytes(words[:2], spec.word_order))[0]
    if dt == "FLOAT64":
        return struct.unpack(">d", _words_to_bytes(words[:4], spec.word_order))[0]
    if dt == "STRING":
        raw = _words_to_bytes(words[: spec.length], spec.word_order)
        return raw.split(b"\x00")[0].decode("ascii", errors="replace").strip()
    raise ValueError(f"{spec.parameter_name}: unsupported data type {spec.data_type}")


def word_count(spec: RegisterSpec) -> int:
    dt = spec.data_type.upper()
    if dt in ("UINT16", "INT16", "BIT"):
        return 1
    if dt in ("UINT32", "INT32", "FLOAT32"):
        return 2
    if dt == "FLOAT64":
        return 4
    return max(1, spec.length)


def apply_scaling(value: Any, spec: RegisterSpec) -> Any:
    if isinstance(value, bool) or isinstance(value, str):
        return value
    return value * spec.scale + spec.offset


class ModbusTcpAdapter(ProtocolAdapter):
    protocol = "MODBUS_TCP"

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        *,
        timeout_s: float = 3.0,
        retries: int = 2,
        descriptor: str = "",
    ) -> None:
        super().__init__(descriptor=descriptor or f"modbus-tcp://{host}:{port}/{unit_id}")
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout_s = timeout_s
        self.retries = retries
        self._client: Any | None = None

    # --- lifecycle --------------------------------------------------------
    def _build_client(self) -> Any:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ProtocolError(
                "pymodbus is not installed; Modbus TCP is unavailable. "
                "Install it with: pip install pymodbus"
            ) from exc
        return ModbusTcpClient(host=self.host, port=self.port, timeout=self.timeout_s)

    def connect(self) -> None:
        if self._client is None:
            self._client = self._build_client()
        if not self._client.connect():
            raise ProtocolError(f"Could not open TCP connection to {self.host}:{self.port}")

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    def test_connection(self) -> ConnectionInfo:
        started = time.perf_counter()
        try:
            self.connect()
        except ProtocolError as exc:
            return ConnectionInfo(ok=False, detail=str(exc))
        latency = (time.perf_counter() - started) * 1000.0
        return ConnectionInfo(
            ok=True,
            detail=(
                f"TCP connection to {self.host}:{self.port} established. "
                "This confirms the socket only — it does not validate the unit ID "
                "or the register map."
            ),
            latency_ms=round(latency, 2),
        )

    # --- reading ----------------------------------------------------------
    def _read_raw(self, spec: RegisterSpec) -> list[int]:
        if spec.function_code not in READ_FUNCTION_CODES:
            raise ProtocolError(
                f"function code {spec.function_code} is not a read function; "
                "PowerTrace AI performs no Modbus writes."
            )
        assert self._client is not None
        count = word_count(spec)
        kwargs: dict[str, Any] = {"address": spec.address, "count": count}
        # pymodbus 3.x renamed the slave kwarg across minor versions; try both
        # rather than pinning users to one point release.
        for slave_kw in ("slave", "unit", None):
            call_kwargs = dict(kwargs)
            if slave_kw:
                call_kwargs[slave_kw] = self.unit_id
            try:
                if spec.function_code == 1:
                    rr = self._client.read_coils(**call_kwargs)
                elif spec.function_code == 2:
                    rr = self._client.read_discrete_inputs(**call_kwargs)
                elif spec.function_code == 3:
                    rr = self._client.read_holding_registers(**call_kwargs)
                else:
                    rr = self._client.read_input_registers(**call_kwargs)
                break
            except TypeError:
                continue
        else:  # pragma: no cover - defensive
            raise ProtocolError("incompatible pymodbus client signature")

        if rr is None or (hasattr(rr, "isError") and rr.isError()):
            raise ProtocolError(f"Modbus exception reading {spec.address}: {rr}")
        if spec.function_code in _BIT_FUNCTION_CODES:
            bits = list(getattr(rr, "bits", []))[:count]
            return [1 if b else 0 for b in bits] or [0]
        return list(getattr(rr, "registers", []))

    def read(self, specs: list[RegisterSpec]) -> list[Reading]:
        readings: list[Reading] = []
        for spec in specs:
            last_error: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    if self._client is None:
                        self.connect()
                    words = self._read_raw(spec)
                    if spec.function_code in _BIT_FUNCTION_CODES:
                        raw: Any = bool(words[0])
                    else:
                        raw = decode_words(words, spec)
                    value = apply_scaling(raw, spec)
                    readings.append(
                        Reading(
                            parameter_name=spec.parameter_name,
                            value=value,
                            unit=spec.unit,
                            quality=Quality.GOOD,
                            source=DataSource.CONTROLLER,
                            normalized_key=spec.normalized_key,
                            source_detail=(
                                f"{self.descriptor} fc{spec.function_code}@{spec.address}"
                            ),
                            timestamp=utcnow(),
                        )
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                    last_error = exc
                    self.close()
                    if attempt < self.retries:
                        time.sleep(min(0.25 * (attempt + 1), 1.0))
            else:
                readings.append(
                    Reading(
                        parameter_name=spec.parameter_name,
                        value=None,
                        unit=spec.unit,
                        quality=Quality.TIMEOUT if _is_timeout(last_error) else Quality.BAD,
                        source=DataSource.CONTROLLER,
                        normalized_key=spec.normalized_key,
                        source_detail=self.descriptor,
                        error=str(last_error),
                    )
                )
        return readings


def _is_timeout(exc: Exception | None) -> bool:
    text = str(exc).lower() if exc else ""
    return "timeout" in text or "timed out" in text
