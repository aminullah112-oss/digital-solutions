"""Tests for the rules that make this tool trustworthy.

If any of these fail, the application is telling a technician something it
cannot support, which is worse than telling them nothing.
"""
from __future__ import annotations

import pytest

from app.domain import ComparisonResult, Confidence, ControlNotPermitted, DataSource, Quality
from app.protocols.base import ProtocolAdapter
from app.protocols.modbus_tcp import ModbusTcpAdapter, READ_FUNCTION_CODES
from app.protocols.simulator import SimulatorAdapter
from app.services.ai import validate_response
from app.services.expected_actual import Expectation, compare
from app.services.measurement_safety import blocking, validate_channel


def test_no_adapter_can_write():
    """Every adapter refuses control, including future ones."""
    from app.protocols.future import CanJ1939Adapter, ModbusRtuAdapter, MqttAdapter, OpcUaAdapter

    adapters = [
        ModbusTcpAdapter("192.0.2.1"),
        SimulatorAdapter("test-write"),
        ModbusRtuAdapter(), CanJ1939Adapter(), OpcUaAdapter(), MqttAdapter(),
    ]
    for adapter in adapters:
        with pytest.raises(ControlNotPermitted):
            adapter.write(1, 1)


def test_write_is_defined_on_the_base_class():
    """The refusal lives on the interface so a new adapter inherits it."""
    assert "write" in ProtocolAdapter.__dict__


def test_only_read_function_codes_are_supported():
    assert READ_FUNCTION_CODES == {1, 2, 3, 4}
    assert 5 not in READ_FUNCTION_CODES   # write single coil
    assert 6 not in READ_FUNCTION_CODES   # write single register
    assert 16 not in READ_FUNCTION_CODES  # write multiple registers


def test_controller_state_is_not_a_measurement():
    """A controller reporting 24 V must not satisfy a voltage expectation."""
    result = compare(Expectation(24.0), 24.0, measured_source=DataSource.CONTROLLER)
    assert result.result is ComparisonResult.NOT_MEASURED
    assert "not a physical measurement" in result.reason


def test_unmeasured_point_is_not_a_pass():
    result = compare(Expectation(24.0), None)
    assert result.result is ComparisonResult.NOT_MEASURED
    assert result.result is not ComparisonResult.NORMAL


def test_bad_quality_measurement_is_not_compared():
    result = compare(Expectation(24.0), 24.0, measured_quality=Quality.TIMEOUT)
    assert result.result is ComparisonResult.NOT_MEASURED


def test_abnormal_when_voltage_is_absent():
    result = compare(Expectation(24.0, tolerance_pct=10.0), 0.0)
    assert result.result is ComparisonResult.ABNORMAL


def test_abnormal_when_voltage_present_but_expected_zero():
    result = compare(Expectation(0.0), 24.0)
    assert result.result is ComparisonResult.ABNORMAL


def test_direct_connection_to_medium_voltage_is_refused():
    checks = validate_channel({
        "input_type": "VOLTAGE_AC", "signal_conditioning": "DIRECT",
        "nominal_circuit_voltage_v": 4160.0, "max_rated_input": 600.0,
        "isolation_rating_v": 600.0,
    })
    codes = {c.code for c in blocking(checks)}
    assert "DIRECT_CONNECTION_REFUSED" in codes


def test_pt_connection_to_medium_voltage_is_accepted():
    checks = validate_channel({
        "input_type": "VOLTAGE_AC", "signal_conditioning": "PT",
        "conditioning_ratio": 34.67, "nominal_circuit_voltage_v": 4160.0,
        "max_rated_input": 150.0, "isolation_rating_v": 4800.0,
        "calibration_due_at": "2099-01-01T00:00:00+00:00",
    })
    assert blocking(checks) == []
    assert any(c.code == "MEDIUM_VOLTAGE" for c in checks)


def test_over_range_input_is_refused():
    checks = validate_channel({
        "input_type": "VOLTAGE_DC", "signal_conditioning": "DIRECT",
        "nominal_circuit_voltage_v": 48.0, "max_rated_input": 10.0,
        "isolation_rating_v": 300.0,
    })
    assert any(c.code == "OVER_RANGE" for c in blocking(checks))


def test_ai_cannot_claim_measurement_confirmation():
    result = validate_response(
        {"problem_summary": "ok", "confidence": Confidence.CONFIRMED_BY_MEASUREMENT.value},
        {"deterministic_findings": [], "measurements": {}},
    )
    assert result["confidence"] != Confidence.CONFIRMED_BY_MEASUREMENT.value


def test_ai_numbers_outside_the_evidence_are_flagged():
    payload = {"deterministic_findings": [], "measurements": {}, "values": {"v": 24.1}}
    result = validate_response(
        {"problem_summary": "TB23-14 reads 480 V", "confidence": "LIKELY"}, payload)
    assert "480" in result["unsupported_values"]
    assert result["confidence"] == Confidence.UNVERIFIED.value


def test_ai_evidence_comes_from_the_engine_not_the_model():
    payload = {"deterministic_findings": [{"rule_key": "real_rule"}], "measurements": {}}
    result = validate_response(
        {"problem_summary": "x", "evidence": [{"rule_key": "invented"}], "confidence": "LIKELY"},
        payload)
    assert result["evidence"] == [{"rule_key": "real_rule"}]


def test_simulated_values_stay_tagged_simulated():
    from app.protocols.base import RegisterSpec
    from app.services.normalization import normalize

    adapter = SimulatorAdapter("tag-test")
    readings = adapter.read([RegisterSpec("voltage_L1_L2", 0, normalized_key="voltage_L1_L2")])
    assert readings[0].quality is Quality.SIMULATED
    assert readings[0].source is DataSource.SIMULATED
    normalized = normalize(readings, simulated=True)
    assert normalized["voltage_L1_L2"]["quality"] == "SIMULATED"
    assert normalized["voltage_L1_L2"]["source"] == "SIMULATED"


def test_production_refuses_a_default_secret_key():
    """A refused start must happen before anything touches the database.

    Seeding first meant a production start that was correctly refused still
    wrote a default-password administrator row — the check creating the very
    hole it exists to close.
    """
    from app.config import InsecureConfiguration, Settings, check_production_config

    settings = Settings(environment="production")
    with pytest.raises(InsecureConfiguration, match="POWERTRACE_SECRET_KEY"):
        check_production_config(settings, {"POWERTRACE_ADMIN_PASSWORD": "set"})


def test_production_refuses_a_default_admin_password():
    from app.config import InsecureConfiguration, Settings, check_production_config

    settings = Settings(environment="production", secret_key="a-real-secret-key")
    with pytest.raises(InsecureConfiguration, match="POWERTRACE_ADMIN_PASSWORD"):
        check_production_config(settings, {})


def test_development_is_left_alone():
    """The guard must not make a laptop install refuse to run."""
    from app.config import Settings, check_production_config

    check_production_config(Settings(environment="development"), {})


def test_the_guard_runs_before_the_database_is_created():
    """Ordering is the whole point, so assert it rather than trusting it."""
    import inspect

    from app import main

    source = inspect.getsource(main.lifespan)
    assert source.index("check_production_config") < source.index("init_db()")
