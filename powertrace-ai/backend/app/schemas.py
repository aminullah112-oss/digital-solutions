"""Request/response models.

Response envelopes keep provenance explicit: anything that could be mistaken
for a measurement carries `source` and `quality`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain import DataType, NodeType, Protocol, Role, Severity, WordOrder


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -----------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    permissions: list[str]


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    email: str
    full_name: str = ""
    password: str = Field(min_length=8)
    role: Role = Role.VIEWER


# --- Projects -------------------------------------------------------------
class ProjectIn(BaseModel):
    name: str
    site: str = ""
    panel: str = ""
    description: str = ""
    nominal_voltage_v: float | None = None
    nominal_frequency_hz: float | None = None
    control_voltage_v: float | None = None


class ProjectOut(ORMModel):
    id: int
    name: str
    site: str
    panel: str
    description: str
    is_demo: bool
    nominal_voltage_v: float | None
    nominal_frequency_hz: float | None
    control_voltage_v: float | None
    created_at: datetime


# --- Controllers ----------------------------------------------------------
class ProtocolConfigIn(BaseModel):
    protocol: Protocol = Protocol.MODBUS_TCP
    host: str | None = None
    port: int | None = 502
    unit_id: int = 1
    poll_interval_ms: int = Field(default=1000, ge=100, le=600_000)
    timeout_s: float = 3.0
    retries: int = 2
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("host")
    @classmethod
    def host_required_for_tcp(cls, v, info):
        return v


class ControllerIn(BaseModel):
    project_id: int
    name: str
    manufacturer: str = ""
    model: str = ""
    controller_type: str = ""
    description: str = ""
    enabled: bool = True
    is_simulated: bool = False
    register_map_id: int | None = None
    protocol: ProtocolConfigIn = Field(default_factory=ProtocolConfigIn)


class ControllerUpdate(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    controller_type: str | None = None
    description: str | None = None
    enabled: bool | None = None
    register_map_id: int | None = None
    protocol: ProtocolConfigIn | None = None


class ControllerOut(ORMModel):
    id: int
    project_id: int
    name: str
    manufacturer: str
    model: str
    controller_type: str
    description: str
    enabled: bool
    is_simulated: bool
    connection_state: str
    last_ok_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    register_map_id: int | None
    protocol: ProtocolConfigIn | None = None
    register_map_verified: bool | None = None


class ConnectionTestOut(BaseModel):
    ok: bool
    detail: str
    latency_ms: float | None = None
    checked_at: datetime


# --- Register maps --------------------------------------------------------
class RegisterIn(BaseModel):
    parameter_name: str
    address: int
    function_code: int = 3
    data_type: DataType = DataType.UINT16
    word_order: WordOrder = WordOrder.BIG
    length: int = 1
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    description: str = ""
    bit_position: int | None = None
    normalized_key: str = ""
    source: str = ""

    @field_validator("function_code")
    @classmethod
    def read_only_functions(cls, v: int) -> int:
        if v not in (1, 2, 3, 4):
            raise ValueError(
                "only read function codes (1, 2, 3, 4) are accepted; "
                "PowerTrace AI performs no writes"
            )
        return v


class RegisterMapIn(BaseModel):
    name: str
    controller_type: str = ""
    manufacturer: str = ""
    model: str = ""
    source_document: str = Field(
        default="",
        description="The document and revision the addresses were taken from. Required "
                    "before the map can be marked verified.",
    )
    notes: str = ""
    registers: list[RegisterIn] = Field(default_factory=list)


class RegisterMapOut(ORMModel):
    id: int
    name: str
    controller_type: str
    manufacturer: str
    model: str
    source_document: str
    verified: bool
    verified_by: str
    notes: str
    is_simulator_only: bool
    register_count: int = 0


# --- Measurements ---------------------------------------------------------
class MeasurementDeviceIn(BaseModel):
    project_id: int
    name: str
    manufacturer: str = ""
    model: str = ""
    transport: str = "MODBUS_TCP"
    host: str | None = None
    port: int | None = None
    unit_id: int = 1
    is_simulated: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class MeasurementChannelIn(BaseModel):
    device_id: int
    channel_tag: str
    description: str = ""
    input_type: str = "VOLTAGE_DC"
    max_rated_input: float | None = None
    max_rated_input_unit: str = "V"
    isolation_rating_v: float | None = None
    isolated: bool = False
    signal_conditioning: str = "DIRECT"
    conditioning_ratio: float = 1.0
    conditioning_note: str = ""
    scale: float = 1.0
    offset: float = 0.0
    unit: str = "V"
    calibrated_at: datetime | None = None
    calibration_due_at: datetime | None = None
    calibration_reference: str = ""
    circuit_node_id: int | None = None
    terminal_id: int | None = None
    nominal_circuit_voltage_v: float | None = None


class MeasurementIn(BaseModel):
    project_id: int
    value: float
    unit: str = "V"
    channel_id: int | None = None
    circuit_node_id: int | None = None
    terminal_id: int | None = None
    method: Literal["GATEWAY", "MANUAL", "SIM"] = "MANUAL"
    instrument: str = ""
    technician: str = ""
    notes: str = ""
    diagnostic_session_id: int | None = None
    timestamp: datetime | None = None


class MeasurementOut(ORMModel):
    id: int
    project_id: int
    channel_id: int | None
    circuit_node_id: int | None
    terminal_id: int | None
    value: float
    unit: str
    quality: str
    source: str
    method: str
    instrument: str
    technician: str
    notes: str
    timestamp: datetime


# --- Diagnostics ----------------------------------------------------------
class DiagnosticSessionIn(BaseModel):
    project_id: int
    controller_id: int | None = None
    title: str
    fault_category: str = "GENERAL"
    symptom: str = ""
    technician: str = ""
    start_node_key: str | None = None
    run_ai: bool = False


class DiagnosticStepOut(ORMModel):
    id: int
    sequence: int
    title: str
    instruction: str
    expected: dict[str, Any] | None
    actual: dict[str, Any] | None
    status: str
    evidence: list[Any]
    next_action: str
    circuit_node_key: str
    requires_measurement: bool
    safety_notice: str
    notes: str
    completed_at: datetime | None


class DiagnosticSessionOut(ORMModel):
    id: int
    project_id: int
    controller_id: int | None
    title: str
    fault_category: str
    symptom: str
    status: str
    technician: str
    opened_at: datetime
    closed_at: datetime | None
    resolution: str
    unresolved_items: list[Any]
    findings: list[Any]
    ai_analysis: dict[str, Any] | None
    steps: list[DiagnosticStepOut] = Field(default_factory=list)


class StepUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    actual: dict[str, Any] | None = None


class SessionUpdate(BaseModel):
    status: str | None = None
    resolution: str | None = None
    unresolved_items: list[str] | None = None


# --- Alarms ---------------------------------------------------------------
class AlarmOut(ORMModel):
    id: int
    project_id: int
    controller_id: int | None
    code: str
    description: str
    description_source: str
    severity: Severity
    source: str
    is_active: bool
    acknowledged: bool
    acknowledged_by: str
    raised_at: datetime
    cleared_at: datetime | None


class AlarmDefinitionIn(BaseModel):
    catalogue: str
    code: str
    description: str
    severity: Severity = Severity.ALARM
    source_document: str = ""
    recommended_action: str = ""


# --- Circuit --------------------------------------------------------------
class CircuitNodeIn(BaseModel):
    project_id: int
    key: str
    label: str = ""
    node_type: NodeType = NodeType.UNKNOWN
    controller_id: int | None = None
    controller_signal: str = ""
    nominal_voltage_v: float | None = None
    x: float | None = None
    y: float | None = None
    verified: bool = False


class ReportIn(BaseModel):
    project_id: int
    diagnostic_session_id: int | None = None
    title: str = ""
    technician: str = ""
