"""Fault tree with live status per branch.

Each branch reports one of:
  RULED_OUT      a measurement or a controller value excludes it
  SUSPECT        evidence points at it
  UNVERIFIED     nothing has been checked yet
  NOT_MEASURED   it can only be settled by a measurement nobody has taken

Nothing is marked RULED_OUT on inference alone.
"""
from __future__ import annotations

from typing import Any

from ..domain import NodeType

RULED_OUT, SUSPECT, UNVERIFIED, NOT_MEASURED = "RULED_OUT", "SUSPECT", "UNVERIFIED", "NOT_MEASURED"

TREES: dict[str, dict[str, Any]] = {
    "BREAKER_FAIL_TO_CLOSE": {
        "label": "Breaker does not close",
        "children": [
            {"id": "gen_not_ready", "label": "Generator not ready", "children": [
                {"id": "voltage_incorrect", "label": "Voltage outside limits",
                 "check": {"signal": "voltage_L1_L2"}},
                {"id": "frequency_incorrect", "label": "Frequency outside limits",
                 "check": {"signal": "frequency"}},
                {"id": "protection_active", "label": "Protection / shutdown active",
                 "check": {"alarm_severity": "SHUTDOWN"}},
            ]},
            {"id": "close_command_absent", "label": "Close command absent",
             "check": {"signal": "breaker_close_command", "expect_true": True}},
            {"id": "control_voltage_missing", "label": "Control voltage missing",
             "check": {"node_type": NodeType.SOURCE.value}},
            {"id": "relay_not_energized", "label": "Relay not energized",
             "check": {"node_type": NodeType.RELAY_COIL.value}},
            {"id": "fuse_open", "label": "Fuse open",
             "check": {"node_type": NodeType.FUSE.value}},
            {"id": "wiring_discontinuity", "label": "Wiring discontinuity",
             "check": {"discontinuity": True}},
            {"id": "breaker_mechanism", "label": "Breaker mechanism / close coil",
             "check": {"node_type": NodeType.BREAKER.value}},
        ],
    },
    "BREAKER_FAIL_TO_OPEN": {
        "label": "Breaker does not open",
        "children": [
            {"id": "open_command_absent", "label": "Open command absent",
             "check": {"signal": "breaker_close_command", "expect_true": False}},
            {"id": "trip_circuit", "label": "Trip circuit open",
             "check": {"node_type": NodeType.RELAY_CONTACT.value}},
            {"id": "control_voltage_missing", "label": "Control voltage missing",
             "check": {"node_type": NodeType.SOURCE.value}},
            {"id": "mechanism", "label": "Breaker mechanism / trip coil",
             "check": {"node_type": NodeType.BREAKER.value}},
        ],
    },
    "CONTROL_POWER": {
        "label": "Control power fault",
        "children": [
            {"id": "supply", "label": "Supply / charger output",
             "check": {"node_type": NodeType.SOURCE.value}},
            {"id": "protection", "label": "Upstream protection open",
             "check": {"node_type": NodeType.FUSE.value}},
            {"id": "distribution", "label": "Distribution wiring",
             "check": {"discontinuity": True}},
        ],
    },
}


def build(fault_category: str, evidence: dict[str, Any],
          discontinuities: list[dict] | None = None) -> dict[str, Any]:
    tree = TREES.get(fault_category)
    if tree is None:
        return {
            "label": fault_category or "Fault",
            "status": UNVERIFIED,
            "children": [],
            "note": "No fault tree is defined for this category.",
        }
    return _annotate({"id": "root", **tree}, evidence, discontinuities or [])


def _annotate(branch: dict[str, Any], evidence: dict, discontinuities: list[dict]) -> dict:
    children = [_annotate(c, evidence, discontinuities) for c in branch.get("children", [])]
    if children:
        status = SUSPECT if any(c["status"] == SUSPECT for c in children) else (
            RULED_OUT if all(c["status"] == RULED_OUT for c in children) else
            NOT_MEASURED if any(c["status"] == NOT_MEASURED for c in children) else UNVERIFIED
        )
        return {**branch, "children": children, "status": status}

    status, detail = _evaluate(branch.get("check") or {}, evidence, discontinuities)
    return {**branch, "children": [], "status": status, "detail": detail}


def _evaluate(check: dict, evidence: dict, discontinuities: list[dict]) -> tuple[str, str]:
    values = evidence["controller_values"]
    statuses = evidence["node_status"]
    graph_nodes = evidence["graph"]["nodes"]

    if check.get("discontinuity"):
        if discontinuities:
            seg = discontinuities[0]["between"]
            return SUSPECT, f"Measured discontinuity between {seg[0]} and {seg[1]}."
        return NOT_MEASURED, "No pair of measurements brackets a discontinuity."

    if "signal" in check:
        env = values.get(check["signal"])
        if env is None or env.get("value") is None:
            return UNVERIFIED, "No live value for this signal."
        if "expect_true" in check:
            asserted = bool(env.get("value"))
            wanted = check["expect_true"]
            if asserted == wanted:
                return RULED_OUT, (
                    f"Controller reports {check['signal']} = {env.get('value')} "
                    "(controller state, not a measurement)."
                )
            return SUSPECT, f"Controller reports {check['signal']} = {env.get('value')}."
        return UNVERIFIED, (
            f"{check['signal']} = {env.get('value')} {env.get('unit', '')} "
            "— compare against this machine's configured limits."
        )

    if "alarm_severity" in check:
        hits = [a for a in evidence["alarms"] if a.get("severity") == check["alarm_severity"]]
        if hits:
            return SUSPECT, f"{len(hits)} active {check['alarm_severity']}: " + \
                ", ".join(a.get("code", "?") for a in hits[:4])
        return RULED_OUT, f"No active {check['alarm_severity']} reported by the controller."

    if "node_type" in check:
        keys = [k for k, n in graph_nodes.items() if n.get("node_type") == check["node_type"]]
        if not keys:
            return UNVERIFIED, "No node of this type in the circuit model."
        results = {k: statuses.get(k, {}).get("status", "NOT MEASURED") for k in keys}
        if any(v == "FAULT" for v in results.values()):
            bad = [k for k, v in results.items() if v == "FAULT"]
            return SUSPECT, "Measured outside expectation: " + ", ".join(bad)
        if all(v == "NORMAL" for v in results.values()):
            return RULED_OUT, "All points measured within expectation: " + ", ".join(keys)
        return NOT_MEASURED, "Not measured: " + ", ".join(
            k for k, v in results.items() if v in ("NOT MEASURED", "NO EXPECTATION")
        )

    return UNVERIFIED, ""
