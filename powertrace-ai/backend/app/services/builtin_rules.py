"""Built-in, vendor-neutral diagnostic rules.

These encode general electrical control practice, not any particular panel:
a fuse with voltage on one side and none on the other is open, a coil at
rated voltage whose contact output is dead points at the contact or its
wiring, a command with no measurement anywhere is unverified.

Nothing here assumes a Caterpillar signal name, a register address, or a
site-specific tag.  Site rules are added as project-scoped rows.
"""
from __future__ import annotations

from ..domain import Confidence, Severity

BUILTIN_RULES: list[dict] = [
    {
        "key": "command_present_feedback_absent",
        "name": "Close command present, breaker feedback absent",
        "fault_category": "BREAKER_FAIL_TO_CLOSE",
        "priority": 10,
        "conditions": {"all": [
            {"kind": "controller_signal", "key": "breaker_close_command", "op": "is_true"},
            {"kind": "controller_signal", "key": "breaker_closed_feedback", "op": "is_false"},
        ]},
        "conclusion": {
            "confidence": Confidence.UNVERIFIED.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "The controller is commanding the breaker closed and is not seeing closed "
                "feedback. This states the controller's view only; it does not identify "
                "where the close circuit is broken."
            ),
            "recommended_test": (
                "Trace the close circuit and measure at each accessible point, starting at "
                "the controller output terminal, using appropriately rated test equipment."
            ),
            "missing_information": [
                "No physical measurements in the close circuit.",
                "Breaker position by direct observation (mechanical indicator).",
            ],
        },
    },
    {
        "key": "coil_energized_contact_dead",
        "name": "Relay coil at rated voltage, contact output dead",
        "fault_category": "BREAKER_FAIL_TO_CLOSE",
        "priority": 20,
        "conditions": {"all": [
            {"kind": "comparison", "node": "type:RELAY_COIL", "results": ["NORMAL"]},
            {"kind": "comparison", "node": "type:RELAY_CONTACT", "results": ["ABNORMAL"]},
        ]},
        "conclusion": {
            "confidence": Confidence.CONFIRMED_BY_MEASUREMENT.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "A relay coil measures at its expected voltage while the measured voltage "
                "downstream of its contact is outside tolerance. The measurements locate a "
                "discontinuity at the contact or in the wiring downstream of it."
            ),
            "recommended_test": (
                "With the circuit isolated and proved dead, check contact continuity across "
                "the relay in the energized and de-energized states, then check the wiring "
                "from the contact output to the next terminal."
            ),
        },
    },
    {
        "key": "fuse_open_measured",
        "name": "Voltage present upstream of fuse, absent downstream",
        "fault_category": "CONTROL_POWER",
        "priority": 15,
        "conditions": {"all": [
            {"kind": "comparison", "node": "type:FUSE", "results": ["ABNORMAL"]},
        ]},
        "conclusion": {
            "confidence": Confidence.LIKELY.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "Measured voltage across a protective device is inconsistent with its "
                "expected value, which is consistent with an open fuse or an open "
                "disconnect in that branch."
            ),
            "recommended_test": (
                "Isolate the branch, prove dead, then check the fuse element for continuity. "
                "If the fuse is open, find the cause before replacing it."
            ),
        },
    },
    {
        "key": "control_voltage_low",
        "name": "Control voltage below expectation",
        "fault_category": "CONTROL_POWER",
        "priority": 5,
        "conditions": {"any": [
            {"kind": "controller_signal", "key": "control_voltage", "op": "<", "value": 18.0},
            {"kind": "comparison", "node": "type:SOURCE", "results": ["ABNORMAL"]},
        ]},
        "conclusion": {
            "confidence": Confidence.LIKELY.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "Control power is below the expected level. Every downstream symptom in this "
                "panel should be re-evaluated after control power is restored — a low control "
                "bus produces misleading secondary faults."
            ),
            "recommended_test": (
                "Measure the control bus at its source and at the first distribution terminal. "
                "Check the control power supply, its upstream protection and the battery/charger "
                "if the bus is DC."
            ),
        },
    },
    {
        "key": "commanded_output_not_measured",
        "name": "Controller output commanded, circuit not measured",
        "fault_category": "GENERAL",
        "priority": 90,
        "conditions": {"all": [
            {"kind": "controller_signal", "key": "breaker_close_command", "op": "is_true"},
            {"kind": "node_status", "node": "type:CONTROLLER_OUTPUT",
             "status": ["NOT MEASURED"]},
        ]},
        "conclusion": {
            "confidence": Confidence.UNVERIFIED.value,
            "severity": Severity.WARNING.value,
            "finding": (
                "The controller reports the output as commanded, but no physical measurement "
                "exists at the output terminal. Controller state is not evidence of voltage on "
                "a terminal: an output driver, its supply or the field wiring can all fail with "
                "the controller still reporting the command."
            ),
            "recommended_test": (
                "Measure at the controller output terminal with respect to the control "
                "reference, using appropriately rated test equipment."
            ),
            "missing_information": ["Terminal voltage at the controller output."],
        },
    },
    {
        "key": "generator_not_ready_voltage",
        "name": "Generator output voltage outside expectation",
        "fault_category": "BREAKER_FAIL_TO_CLOSE",
        "priority": 30,
        "conditions": {"any": [
            {"kind": "alarm", "severity": Severity.SHUTDOWN.value},
            {"kind": "controller_signal", "key": "frequency", "op": "<", "value": 57.0},
        ]},
        "conclusion": {
            "confidence": Confidence.POSSIBLE.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "The controller is reporting conditions that would normally block a close "
                "permissive. Check the generator's readiness conditions before investigating "
                "the close circuit — a healthy close circuit will not close against a blocked "
                "permissive."
            ),
            "recommended_test": (
                "Review the controller's generator-ready and protection status, and confirm "
                "voltage and frequency against the configured limits for this machine."
            ),
        },
    },
    {
        "key": "communication_lost",
        "name": "Controller communication lost",
        "fault_category": "COMMUNICATION",
        "priority": 1,
        "conditions": {"any": [
            {"kind": "alarm", "code": "COMM_LOST"},
            {"kind": "alarm", "code": "SIM-COM"},
        ]},
        "conclusion": {
            "confidence": Confidence.LIKELY.value,
            "severity": Severity.ALARM.value,
            "finding": (
                "Communication with the controller is down, so no controller-reported value "
                "on this screen is current. Values shown for this controller are historical."
            ),
            "recommended_test": (
                "Check the network path to the controller: link lights, switch port, IP "
                "configuration, and the controller's own communication settings."
            ),
        },
    },
]
