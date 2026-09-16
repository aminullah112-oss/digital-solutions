"""Diagnostic engine: evidence assembly, rule evaluation, discontinuity
localization and procedure generation.

Order matters.  Deterministic work happens first and is complete on its own;
the AI layer (services/ai.py) is handed the finished evidence package and can
only add interpretation on top of it.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import (
    ComparisonResult, Confidence, DataSource, MV_SAFETY_NOTICE, NodeType, Severity, utcnow,
)
from ..models import (
    Alarm, CircuitNode, Controller, DiagnosticSession, DiagnosticStep, Terminal,
    TroubleshootingRule,
)
from . import circuit_graph as cg
from .builtin_rules import BUILTIN_RULES
from .rules import Context, Finding, evaluate_rule
from .terminal_status import terminal_status
from .value_store import store

#: Points at which voltage is considered "present" for continuity analysis,
#: as a fraction of the expected value.  Deliberately conservative: this is
#: used to locate a break, never to declare a circuit safe.
PRESENT_FRACTION = 0.7
ABSENT_FRACTION = 0.2


def controller_values(db: Session, project_id: int) -> dict[str, dict]:
    """Merged live values for the project's controllers, keyed by signal."""
    merged: dict[str, dict] = {}
    for controller in db.scalars(select(Controller).where(Controller.project_id == project_id)):
        for key, env in store.latest(controller.id).items():
            merged.setdefault(key, {**env, "controller_id": controller.id,
                                    "controller_name": controller.name})
    return merged


def active_alarms(db: Session, project_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Alarm).where(Alarm.project_id == project_id, Alarm.is_active.is_(True))
        .order_by(Alarm.raised_at.desc())
    ).all()
    return [{
        "id": a.id, "code": a.code, "description": a.description,
        "description_source": a.description_source,
        "severity": str(a.severity), "source": a.source,
        "raised_at": a.raised_at.isoformat(), "acknowledged": a.acknowledged,
        "controller_id": a.controller_id,
    } for a in rows]


def node_statuses(db: Session, project_id: int, keys: list[str] | None = None) -> dict[str, dict]:
    stmt = select(CircuitNode).where(CircuitNode.project_id == project_id)
    if keys:
        stmt = stmt.where(CircuitNode.key.in_(keys))
    nodes = db.scalars(stmt).all()
    terminals = {
        t.id: t for t in db.scalars(select(Terminal).where(Terminal.project_id == project_id))
    }
    return {
        n.key: terminal_status(db, n, terminals.get(n.terminal_id) if n.terminal_id else None)
        for n in nodes
    }


def build_evidence(
    db: Session, project_id: int, *, scope_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the complete, provenance-tagged evidence package.

    This is the single input to rule evaluation, the fault tree and the AI
    layer, so all three reason about exactly the same facts.
    """
    graph = cg.load_graph(db, project_id)
    statuses = node_statuses(db, project_id, scope_keys)
    values = controller_values(db, project_id)
    alarms = active_alarms(db, project_id)
    return {
        "project_id": project_id,
        "generated_at": utcnow().isoformat(),
        "controller_values": values,
        "alarms": alarms,
        "node_status": statuses,
        "graph": {
            "nodes": graph.nodes,
            "edges": [cg._edge_payload(e) for e in graph.edges],
        },
        "scope_keys": scope_keys or list(graph.nodes),
        "_graph": graph,
    }


def load_rules(db: Session, project_id: int, fault_category: str | None = None) -> list[dict]:
    rows = db.scalars(
        select(TroubleshootingRule)
        .where(TroubleshootingRule.enabled.is_(True))
        .where((TroubleshootingRule.project_id == project_id)
               | (TroubleshootingRule.project_id.is_(None)))
        .order_by(TroubleshootingRule.priority)
    ).all()
    rules = [{
        "key": r.key, "name": r.name, "fault_category": r.fault_category,
        "conditions": r.conditions, "conclusion": r.conclusion, "priority": r.priority,
    } for r in rows]
    if not rules:
        rules = sorted(BUILTIN_RULES, key=lambda r: r["priority"])
    if fault_category:
        rules = [r for r in rules
                 if not r.get("fault_category") or r["fault_category"] == fault_category
                 or r["fault_category"] == "GENERAL"]
    return rules


def evaluate(
    db: Session, project_id: int, *, fault_category: str | None = None,
    scope_keys: list[str] | None = None, evidence: dict | None = None,
) -> dict[str, Any]:
    evidence = evidence or build_evidence(db, project_id, scope_keys=scope_keys)
    ctx = Context(
        controller_values=evidence["controller_values"],
        node_status=evidence["node_status"],
        alarms=evidence["alarms"],
        graph_nodes=evidence["graph"]["nodes"],
        scope_keys=evidence["scope_keys"],
    )
    findings: list[Finding] = []
    for rule in load_rules(db, project_id, fault_category):
        finding = evaluate_rule(rule, ctx)
        if finding:
            findings.append(finding)

    discontinuities = localize_discontinuity(evidence)
    return {
        "findings": [f.as_dict() for f in findings],
        "discontinuities": discontinuities,
        "coverage": measurement_coverage(evidence),
        "generated_at": evidence["generated_at"],
    }


def localize_discontinuity(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Find measured voltage-present / voltage-absent boundaries.

    This is the most useful deterministic output the tool produces: given two
    measured points on a traced path, one with voltage and one without, the
    break is between them. It is stated as a bounded segment, never as a
    named failed part.
    """
    graph: cg.Graph = evidence["_graph"]
    statuses = evidence["node_status"]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for edge in graph.edges:
        src, dst = edge.flow()
        a, b = statuses.get(src), statuses.get(dst)
        if not a or not b:
            continue
        a_state, b_state = _voltage_state(a), _voltage_state(b)
        if a_state == "PRESENT" and b_state == "ABSENT":
            pair = (src, dst)
        elif b_state == "PRESENT" and a_state == "ABSENT":
            pair = (dst, src)
        else:
            continue
        if pair in seen:
            continue
        seen.add(pair)
        upstream, downstream = pair
        out.append({
            "between": [upstream, downstream],
            "via": cg._edge_payload(edge),
            "upstream_measured": statuses[upstream].get("measured"),
            "downstream_measured": statuses[downstream].get("measured"),
            "statement": (
                f"Voltage is present at {upstream} and absent at {downstream}. "
                "Both values are physical measurements, so the discontinuity lies in the "
                "segment between these two points, including the device and terminations in it."
            ),
            "confidence": Confidence.CONFIRMED_BY_MEASUREMENT.value,
            "components_in_segment": _devices_between(graph, upstream, downstream),
        })
    return out


def _voltage_state(status: dict[str, Any]) -> str:
    measured = status.get("measured") or {}
    expected = status.get("expected") or {}
    value, exp = measured.get("value"), expected.get("value")
    if value is None or measured.get("source") not in ("MEASURED", "SIMULATED"):
        return "UNKNOWN"
    if exp is None or exp == 0:
        return "PRESENT" if abs(value) > 1.0 else "ABSENT"
    ratio = abs(value) / abs(exp)
    if ratio >= PRESENT_FRACTION:
        return "PRESENT"
    if ratio <= ABSENT_FRACTION:
        return "ABSENT"
    return "PARTIAL"


def _devices_between(graph: cg.Graph, a: str, b: str) -> list[dict[str, Any]]:
    path = cg.shortest_path(graph, a, b) or [a, b]
    devices = []
    for key in path:
        node = graph.nodes.get(key, {})
        if node.get("node_type") in (
            NodeType.FUSE.value, NodeType.RELAY_CONTACT.value, NodeType.SWITCH.value,
            NodeType.BREAKER.value, NodeType.CONTACTOR.value, NodeType.TERMINAL.value,
            NodeType.CONNECTOR.value, NodeType.WIRE.value,
        ):
            devices.append({"key": key, "label": node.get("label"),
                            "node_type": node.get("node_type")})
    return devices


def measurement_coverage(evidence: dict[str, Any]) -> dict[str, Any]:
    statuses = evidence["node_status"]
    scope = evidence["scope_keys"]
    total = len(scope)
    measured = sum(1 for k in scope
                   if (statuses.get(k, {}).get("measured") or {}).get("value") is not None)
    unmeasured = [k for k in scope
                  if (statuses.get(k, {}).get("measured") or {}).get("value") is None]
    return {
        "nodes_in_scope": total,
        "measured": measured,
        "unmeasured": len(unmeasured),
        "coverage_pct": round(measured / total * 100.0, 1) if total else 0.0,
        "unmeasured_keys": unmeasured[:50],
        "note": (
            "Unmeasured points are shown as NOT MEASURED. No voltage is inferred for them "
            "from controller state or from neighbouring points."
        ),
    }


# --- Troubleshooting procedure -------------------------------------------

def generate_procedure(
    db: Session, session: DiagnosticSession, evidence: dict[str, Any],
) -> list[DiagnosticStep]:
    """Build an ordered procedure for the session's fault category.

    Steps are generated from the circuit graph, so the trace steps name the
    actual components in this panel's close circuit rather than a generic
    checklist.
    """
    graph: cg.Graph = evidence["_graph"]
    values = evidence["controller_values"]
    statuses = evidence["node_status"]
    steps: list[DiagnosticStep] = []
    seq = 1

    def add(title: str, instruction: str, *, expected=None, actual=None,
            node_key: str = "", requires_measurement: bool = False,
            next_action: str = "", evidence_items: list | None = None) -> None:
        nonlocal seq
        node = graph.nodes.get(node_key, {})
        safety = MV_SAFETY_NOTICE if node.get("medium_voltage") else (
            MV_SAFETY_NOTICE if requires_measurement else ""
        )
        steps.append(DiagnosticStep(
            sequence=seq, title=title, instruction=instruction,
            expected=expected, actual=actual,
            status=_step_status(expected, actual),
            evidence=evidence_items or [],
            next_action=next_action, circuit_node_key=node_key,
            requires_measurement=requires_measurement, safety_notice=safety,
        ))
        seq += 1

    category = session.fault_category or "GENERAL"

    if category in ("BREAKER_FAIL_TO_CLOSE", "GENERAL"):
        for key, label, limit_note in (
            ("voltage_L1_L2", "generator voltage", "configured voltage limits"),
            ("frequency", "generator frequency", "configured frequency limits"),
        ):
            env = values.get(key)
            add(
                f"Check {label}",
                f"Read {label} from the controller and compare against the {limit_note} "
                "configured for this machine.",
                expected={"description": f"Within {limit_note}",
                          "source": DataSource.EXPECTATION.value,
                          "note": "Limits are site configuration; they are not assumed here."},
                actual=_actual_from(env),
                next_action="If outside limits, resolve the generator condition first.",
            )
        add(
            "Check the close command at the controller",
            "Confirm the controller is issuing the close command, and note that this is the "
            "controller's reported state, not a measurement at a terminal.",
            expected={"description": "Close command asserted when a close is attempted",
                      "source": DataSource.EXPECTATION.value},
            actual=_actual_from(values.get("breaker_close_command")),
            next_action="If the command is not asserted, the fault is upstream of the "
                        "close circuit: check permissives and protection status.",
        )

    # Circuit-derived steps: walk the close circuit from the controller output.
    start = _close_circuit_start(graph)
    if start:
        trace = cg.trace(graph, start, direction="down", max_depth=10)
        for node in trace["nodes"]:
            key = node["key"]
            status = statuses.get(key, {})
            if node["node_type"] in (NodeType.WIRE.value,):
                continue
            add(
                f"Measure at {node.get('label') or key}",
                f"Measure at {node.get('label') or key} with respect to the circuit reference "
                f"({(node.get('terminal') or {}).get('expected_reference') or 'control common'}) "
                "using appropriately rated test equipment.",
                expected=status.get("expected"),
                actual=status.get("measured"),
                node_key=key,
                requires_measurement=True,
                next_action=(
                    "If the expected voltage is present here, continue downstream. "
                    "If it is absent, the break is between this point and the last point "
                    "where voltage was present."
                ),
                evidence_items=[status.get("controller")] if status.get("controller") else [],
            )
    else:
        add(
            "Trace the circuit",
            "No circuit graph is available for this fault. Import and verify the relevant "
            "schematic page, then re-run the procedure to get circuit-specific steps.",
            next_action="Schematics -> Import.",
        )

    for step in steps:
        step.session_id = session.id
        db.add(step)
    return steps


def _close_circuit_start(graph: cg.Graph) -> str | None:
    outputs = [k for k, n in graph.nodes.items()
               if n["node_type"] == NodeType.CONTROLLER_OUTPUT.value]
    return outputs[0] if outputs else None


def _actual_from(env: dict | None) -> dict | None:
    if not env:
        return {"value": None, "source": DataSource.UNKNOWN.value,
                "note": "No live value available."}
    return {
        "value": env.get("value"), "unit": env.get("unit"),
        "quality": env.get("quality"), "source": env.get("source"),
        "timestamp": env.get("timestamp"),
        "note": "Controller-reported value.",
    }


def _step_status(expected: dict | None, actual: dict | None) -> str:
    if not actual or actual.get("value") is None:
        return "PENDING"
    if not expected or expected.get("value") is None:
        return "INFO"
    from .expected_actual import Expectation, compare
    from ..domain import Quality

    result = compare(
        Expectation(expected.get("value"), expected.get("unit", "V"),
                    expected.get("tolerance_pct", 10.0)),
        actual.get("value"),
        measured_unit=actual.get("unit", "V"),
        measured_quality=Quality(actual.get("quality", "GOOD")),
        measured_source=DataSource(actual.get("source", "UNKNOWN")),
    )
    return {
        ComparisonResult.NORMAL: "PASS",
        ComparisonResult.MARGINAL: "MARGINAL",
        ComparisonResult.ABNORMAL: "FAIL",
    }.get(result.result, "PENDING")
