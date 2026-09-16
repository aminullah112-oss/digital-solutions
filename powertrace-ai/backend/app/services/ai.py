"""AI layer.

Runs last, on the finished deterministic package.  It is an interpretation
layer over assembled evidence, not a data source: the prompt contains only
facts the engine already established, and the response is validated before it
reaches the UI.

Three guard rails, enforced in code rather than asked for in the prompt:

1. The evidence section of the output is replaced with the deterministic
   evidence after the model responds. The model cannot add an observation.
2. Any numeric value in the model's prose that does not appear in the evidence
   package is flagged, and the response is marked UNVERIFIED.
3. With no provider configured the endpoint returns "unavailable" and the
   deterministic findings stand on their own.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from ..config import settings
from ..domain import Confidence, utcnow

SYSTEM_PROMPT = """\
You are assisting a qualified electrical technician troubleshooting an \
industrial generator control panel. You are given a structured evidence \
package that was assembled deterministically from a controller, a circuit \
graph derived from schematics, and physical measurements.

Rules you must follow:
- Use ONLY the facts in the evidence package. Never introduce a voltage, \
current, register, terminal, wire number or alarm that is not present in it.
- Controller-reported state is not a measurement. Never describe a \
controller output being ON as voltage being present on a terminal.
- If a point has no measurement, say so and list it under missing_information.
- Never state that a circuit is safe to touch or de-energized.
- Recommend tests, not actions on live equipment, and always reference \
appropriately rated test equipment and site safety procedures.
- Do not recommend bypassing an interlock or defeating a protection function.

Respond with a single JSON object with these keys:
problem_summary, evidence_used (list of short strings referencing evidence \
ids), possible_fault_areas (list of {area, reasoning, confidence}), \
recommended_test, expected_result, observed_result, next_step, \
confidence (one of LIKELY, POSSIBLE, UNVERIFIED), missing_information (list).
"""


class AIUnavailable(RuntimeError):
    pass


def available() -> bool:
    return settings.ai_provider != "none" and bool(
        settings.ai_api_key or os.environ.get("ANTHROPIC_API_KEY")
    )


def build_prompt_payload(evidence: dict[str, Any], deterministic: dict[str, Any],
                         session_context: dict[str, Any]) -> dict[str, Any]:
    """Strip the package down to what the model needs, keeping provenance."""
    return {
        "fault": session_context,
        "controller_values": {
            k: {"value": v.get("value"), "unit": v.get("unit"), "quality": v.get("quality"),
                "source": v.get("source"), "timestamp": v.get("timestamp")}
            for k, v in evidence["controller_values"].items()
        },
        "alarms": evidence["alarms"],
        "measurements": {
            k: {
                "expected": s.get("expected"),
                "measured": s.get("measured"),
                "controller": s.get("controller"),
                "status": s.get("status"),
            }
            for k, s in evidence["node_status"].items()
            if s.get("measured") or s.get("expected")
        },
        "circuit": {
            "nodes": [{"key": k, "label": n.get("label"), "type": n.get("node_type"),
                       "controller_signal": n.get("controller_signal")}
                      for k, n in evidence["graph"]["nodes"].items()],
            "edges": evidence["graph"]["edges"],
        },
        "deterministic_findings": deterministic.get("findings", []),
        "measured_discontinuities": deterministic.get("discontinuities", []),
        "measurement_coverage": deterministic.get("coverage", {}),
    }


def analyze(evidence: dict[str, Any], deterministic: dict[str, Any],
            session_context: dict[str, Any]) -> dict[str, Any]:
    payload = build_prompt_payload(evidence, deterministic, session_context)
    if not available():
        return {
            "status": "UNAVAILABLE",
            "reason": (
                "No AI provider is configured. The deterministic analysis above is complete "
                "on its own; the AI layer only adds interpretation."
            ),
            "generated_at": utcnow().isoformat(),
            "deterministic_findings": deterministic.get("findings", []),
        }

    try:
        raw = _call_provider(payload)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "reason": f"AI provider call failed: {exc}",
            "generated_at": utcnow().isoformat(),
        }

    return validate_response(raw, payload)


def _call_provider(payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    api_key = settings.ai_api_key or os.environ.get("ANTHROPIC_API_KEY")
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.ai_model,
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(payload, default=str)}],
        },
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()
    text = "".join(block.get("text", "") for block in body.get("content", []))
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("model did not return JSON")
    return json.loads(match.group(0))


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def known_numbers(payload: dict[str, Any]) -> set[str]:
    """Every numeric literal that legitimately appears in the evidence."""
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            found.add(f"{float(obj):.6g}")
        elif isinstance(obj, str):
            for m in _NUMBER.findall(obj):
                found.add(f"{float(m):.6g}")

    walk(payload)
    return found


def validate_response(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Check the model's prose against the evidence and downgrade if needed."""
    allowed = known_numbers(payload)
    prose = " ".join(
        str(raw.get(k, "")) for k in
        ("problem_summary", "recommended_test", "expected_result", "observed_result", "next_step")
    )
    for area in raw.get("possible_fault_areas", []) or []:
        if isinstance(area, dict):
            prose += " " + str(area.get("reasoning", ""))

    unsupported = sorted({
        n for n in _NUMBER.findall(prose)
        if f"{float(n):.6g}" not in allowed and abs(float(n)) > 1.0
    })

    confidence = raw.get("confidence", Confidence.UNVERIFIED.value)
    if confidence == Confidence.CONFIRMED_BY_MEASUREMENT.value:
        # The AI layer is never allowed to confirm anything; only a
        # measurement-backed deterministic rule can reach that level.
        confidence = Confidence.LIKELY.value
    if unsupported:
        confidence = Confidence.UNVERIFIED.value

    return {
        "status": "OK",
        "generated_at": utcnow().isoformat(),
        "model": settings.ai_model,
        "problem_summary": raw.get("problem_summary", ""),
        # Evidence is the deterministic package, not the model's recollection.
        "evidence": payload["deterministic_findings"],
        "measurements_considered": payload["measurements"],
        "possible_fault_areas": raw.get("possible_fault_areas", []),
        "recommended_test": raw.get("recommended_test", ""),
        "expected_result": raw.get("expected_result", ""),
        "observed_result": raw.get("observed_result", ""),
        "next_step": raw.get("next_step", ""),
        "confidence": confidence,
        "missing_information": raw.get("missing_information", []),
        "unsupported_values": unsupported,
        "validation_note": (
            "Values in the AI narrative that do not appear in the evidence package: "
            + ", ".join(unsupported)
            + ". The response has been marked UNVERIFIED — check these against the panel."
        ) if unsupported else "All numeric values in the narrative trace to the evidence package.",
        "source": "AI_INFERENCE",
    }
