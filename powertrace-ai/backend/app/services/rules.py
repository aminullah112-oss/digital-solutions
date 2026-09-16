"""Declarative rule language for the diagnostic engine.

Rules are data so an engineer can add a site rule without a code release, and
so every conclusion can point at the exact rule and the exact evidence that
produced it.

A rule never asserts a fault.  It produces a finding with a confidence level:
CONFIRMED_BY_MEASUREMENT is reachable only when physical measurements support
the conclusion on both sides; everything else is LIKELY, POSSIBLE or
UNVERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..domain import ComparisonResult, Confidence, Quality

Selector = str  # "node:KEY" | "type:FUSE" | "signal:KEY"


@dataclass
class EvidenceItem:
    kind: str
    label: str
    value: Any
    source: str
    quality: str = Quality.GOOD.value
    detail: str = ""
    node_key: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Finding:
    rule_key: str
    title: str
    statement: str
    confidence: Confidence
    suspect_nodes: list[str] = field(default_factory=list)
    recommended_test: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    severity: str = "ALARM"

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_key": self.rule_key,
            "title": self.title,
            "statement": self.statement,
            "confidence": self.confidence.value,
            "suspect_nodes": self.suspect_nodes,
            "recommended_test": self.recommended_test,
            "evidence": [e.as_dict() for e in self.evidence],
            "missing_information": self.missing_information,
            "severity": self.severity,
            "source": "DETERMINISTIC_RULE",
        }


OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: _num(a) > _num(b),
    "<": lambda a, b: _num(a) < _num(b),
    ">=": lambda a, b: _num(a) >= _num(b),
    "<=": lambda a, b: _num(a) <= _num(b),
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "is_true": lambda a, _b: a is True or a == 1,
    "is_false": lambda a, _b: a is False or a == 0,
    "is_null": lambda a, _b: a is None,
    "not_null": lambda a, _b: a is not None,
    "abs_lt": lambda a, b: abs(_num(a)) < _num(b),
    "abs_gte": lambda a, b: abs(_num(a)) >= _num(b),
}


def _num(v: Any) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


class Context:
    """Everything a rule may look at.

    Deliberately narrow: rules see live controller values, node statuses
    (which already separate expected/controller/measured), active alarms and
    the circuit graph.  They cannot see raw registers or reach the network.
    """

    def __init__(
        self,
        *,
        controller_values: dict[str, dict],
        node_status: dict[str, dict],
        alarms: list[dict],
        graph_nodes: dict[str, dict],
        scope_keys: list[str] | None = None,
    ) -> None:
        self.controller_values = controller_values
        self.node_status = node_status
        self.alarms = alarms
        self.graph_nodes = graph_nodes
        self.scope_keys = scope_keys or list(graph_nodes)

    # --- selectors --------------------------------------------------------
    def resolve(self, selector: Selector) -> list[str]:
        if selector.startswith("node:"):
            key = selector[5:]
            return [key] if key in self.node_status or key in self.graph_nodes else []
        if selector.startswith("type:"):
            want = selector[5:].upper()
            return [k for k in self.scope_keys
                    if self.graph_nodes.get(k, {}).get("node_type", "").upper() == want]
        if selector.startswith("signal:"):
            return [selector[7:]]
        return [selector]


def evaluate_condition(cond: dict[str, Any], ctx: Context) -> tuple[bool, list[EvidenceItem]]:
    """Evaluate one condition node; returns (matched, evidence)."""
    if "all" in cond:
        evidence: list[EvidenceItem] = []
        for sub in cond["all"]:
            ok, ev = evaluate_condition(sub, ctx)
            evidence.extend(ev)
            if not ok:
                return False, []
        return True, evidence
    if "any" in cond:
        for sub in cond["any"]:
            ok, ev = evaluate_condition(sub, ctx)
            if ok:
                return True, ev
        return False, []
    if "not" in cond:
        ok, _ = evaluate_condition(cond["not"], ctx)
        return (not ok), []

    kind = cond.get("kind")
    handler = _HANDLERS.get(kind)
    if handler is None:
        return False, []
    return handler(cond, ctx)


def _c_controller_signal(cond, ctx) -> tuple[bool, list[EvidenceItem]]:
    key = cond["key"]
    env = ctx.controller_values.get(key)
    if env is None:
        return False, []
    if cond.get("require_quality", True) and env.get("quality") in ("BAD", "TIMEOUT", "UNKNOWN"):
        return False, []
    op = OPS[cond.get("op", "==")]
    if not op(env.get("value"), cond.get("value")):
        return False, []
    return True, [EvidenceItem(
        kind="controller_signal", label=env.get("display_name") or key,
        value=env.get("value"), source=env.get("source", "CONTROLLER"),
        quality=env.get("quality", "GOOD"),
        detail=f"{key} reported by controller at {env.get('timestamp')}",
    )]


def _c_comparison(cond, ctx) -> tuple[bool, list[EvidenceItem]]:
    wanted = {r.upper() for r in cond.get("results", [])}
    for key in ctx.resolve(cond["node"]):
        status = ctx.node_status.get(key)
        if not status:
            continue
        result = status.get("comparison", {}).get("result")
        if result in wanted:
            measured = status.get("measured") or {}
            return True, [EvidenceItem(
                kind="comparison", label=f"{key} expected vs measured",
                value=measured.get("value"), source=measured.get("source", "UNKNOWN"),
                quality=measured.get("quality", "UNKNOWN"),
                detail=status.get("reason", ""), node_key=key,
            )]
    return False, []


def _c_measured(cond, ctx) -> tuple[bool, list[EvidenceItem]]:
    op = OPS[cond.get("op", "==")]
    for key in ctx.resolve(cond["node"]):
        status = ctx.node_status.get(key)
        measured = (status or {}).get("measured")
        if not measured or measured.get("value") is None:
            continue
        if measured.get("source") not in ("MEASURED", "SIMULATED"):
            continue
        if op(measured["value"], cond.get("value")):
            return True, [EvidenceItem(
                kind="measurement", label=f"{key} measured",
                value=measured["value"], source=measured.get("source", "MEASURED"),
                quality=measured.get("quality", "GOOD"),
                detail=f"{measured['value']} {measured.get('unit', '')} at {key}",
                node_key=key,
            )]
    return False, []


def _c_alarm(cond, ctx) -> tuple[bool, list[EvidenceItem]]:
    code = cond.get("code")
    severity = cond.get("severity")
    for alarm in ctx.alarms:
        if code and alarm.get("code") != code:
            continue
        if severity and alarm.get("severity") != severity:
            continue
        return True, [EvidenceItem(
            kind="alarm", label=alarm.get("code", "alarm"),
            value=alarm.get("description"), source=alarm.get("source", "CONTROLLER"),
            detail=f"raised {alarm.get('raised_at')}",
        )]
    return False, []


def _c_node_status(cond, ctx) -> tuple[bool, list[EvidenceItem]]:
    wanted = {s.upper() for s in cond.get("status", [])}
    for key in ctx.resolve(cond["node"]):
        status = ctx.node_status.get(key)
        if status and status.get("status", "").upper() in wanted:
            return True, [EvidenceItem(
                kind="node_status", label=key, value=status.get("status"),
                source="DERIVED", detail=status.get("reason", ""), node_key=key,
            )]
    return False, []


_HANDLERS = {
    "controller_signal": _c_controller_signal,
    "comparison": _c_comparison,
    "measured": _c_measured,
    "alarm": _c_alarm,
    "node_status": _c_node_status,
}


def evaluate_rule(rule: dict[str, Any], ctx: Context) -> Finding | None:
    conditions = rule.get("conditions") or {}
    if not conditions:
        return None
    matched, evidence = evaluate_condition(conditions, ctx)
    if not matched:
        return None
    conclusion = rule.get("conclusion") or {}
    confidence = Confidence(conclusion.get("confidence", Confidence.POSSIBLE.value))

    # A conclusion may only be stated as measurement-confirmed if physical
    # measurements are actually present in its evidence.  This is enforced
    # here rather than trusted to whoever wrote the rule.
    if confidence is Confidence.CONFIRMED_BY_MEASUREMENT:
        has_measurement = any(e.kind == "measurement" or
                              (e.kind == "comparison" and e.source in ("MEASURED", "SIMULATED"))
                              for e in evidence)
        if not has_measurement:
            confidence = Confidence.UNVERIFIED

    suspects = list(conclusion.get("suspect_nodes", []))
    suspects.extend(e.node_key for e in evidence if e.node_key and e.node_key not in suspects)
    return Finding(
        rule_key=rule.get("key", "unnamed"),
        title=rule.get("name", rule.get("key", "finding")),
        statement=conclusion.get("finding", ""),
        confidence=confidence,
        suspect_nodes=[s for s in suspects if s],
        recommended_test=conclusion.get("recommended_test", ""),
        evidence=evidence,
        missing_information=list(conclusion.get("missing_information", [])),
        severity=conclusion.get("severity", "ALARM"),
    )


NOT_MEASURED = ComparisonResult.NOT_MEASURED.value
ABNORMAL = ComparisonResult.ABNORMAL.value
NORMAL = ComparisonResult.NORMAL.value
