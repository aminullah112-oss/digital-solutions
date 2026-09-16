"""Report generation.

The report body is structured JSON. CSV and a print-ready HTML rendering are
built from it, so an export can be regenerated identically months later.

PDF: produced with ReportLab when it is installed. When it is not, the API
says so and hands back the print-ready HTML rather than a broken file.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy.orm import Session

from ..domain import MV_SAFETY_NOTICE, utcnow
from ..models import Controller, DiagnosticSession, Project

DISCLAIMER = (
    "PowerTrace AI is a diagnostic aid, not a safety-rated protection system. It issues no "
    "control commands. Nothing in this report establishes that any circuit is de-energized. "
    + MV_SAFETY_NOTICE
)


def build_content(db: Session, session: DiagnosticSession) -> dict[str, Any]:
    project = db.get(Project, session.project_id)
    controller = db.get(Controller, session.controller_id) if session.controller_id else None
    evidence = session.evidence_snapshot or {}

    return {
        "generated_at": utcnow().isoformat(),
        "project": {
            "name": project.name if project else "",
            "site": project.site if project else "",
            "panel": project.panel if project else "",
            "is_demo": project.is_demo if project else False,
        },
        "controller": {
            "name": controller.name if controller else "",
            "manufacturer": controller.manufacturer if controller else "",
            "model": controller.model if controller else "",
        },
        "session": {
            "id": session.id,
            "title": session.title,
            "fault_category": session.fault_category,
            "symptom": session.symptom,
            "status": session.status,
            "technician": session.technician,
            "opened_at": session.opened_at.isoformat() if session.opened_at else None,
            "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            "resolution": session.resolution,
            "unresolved_items": session.unresolved_items or [],
        },
        "initial_condition": {
            "controller_values": evidence.get("controller_values", {}),
            "alarms": evidence.get("alarms", []),
        },
        "circuit_trace": evidence.get("trace", {}),
        "measurements": [
            {"node": key, "expected": st.get("expected"), "measured": st.get("measured"),
             "controller": st.get("controller"), "status": st.get("status"),
             "reason": st.get("reason")}
            for key, st in (evidence.get("node_status") or {}).items()
            if st.get("measured") or st.get("expected")
        ],
        "findings": session.findings or [],
        "ai_analysis": session.ai_analysis,
        "steps": [
            {"sequence": s.sequence, "title": s.title, "instruction": s.instruction,
             "expected": s.expected, "actual": s.actual, "status": s.status,
             "evidence": s.evidence, "next_action": s.next_action, "notes": s.notes,
             "safety_notice": s.safety_notice}
            for s in session.steps
        ],
        "disclaimer": DISCLAIMER,
    }


def to_json(content: dict[str, Any]) -> str:
    return json.dumps(content, indent=2, default=str)


def to_csv(content: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "item", "field", "value"])

    def row(section: str, item: str, field: str, value: Any) -> None:
        writer.writerow([section, item, field, "" if value is None else value])

    for key, value in content["session"].items():
        row("session", "", key, value)
    for key, env in content["initial_condition"]["controller_values"].items():
        row("controller_value", key, "value", env.get("value"))
        row("controller_value", key, "unit", env.get("unit"))
        row("controller_value", key, "quality", env.get("quality"))
        row("controller_value", key, "source", env.get("source"))
        row("controller_value", key, "timestamp", env.get("timestamp"))
    for m in content["measurements"]:
        row("measurement", m["node"], "expected",
            (m.get("expected") or {}).get("value"))
        row("measurement", m["node"], "measured", (m.get("measured") or {}).get("value"))
        row("measurement", m["node"], "source", (m.get("measured") or {}).get("source"))
        row("measurement", m["node"], "status", m.get("status"))
    for f in content["findings"]:
        row("finding", f.get("rule_key", ""), "statement", f.get("statement"))
        row("finding", f.get("rule_key", ""), "confidence", f.get("confidence"))
        row("finding", f.get("rule_key", ""), "recommended_test", f.get("recommended_test"))
    for s in content["steps"]:
        row("step", str(s["sequence"]), "title", s["title"])
        row("step", str(s["sequence"]), "status", s["status"])
        row("step", str(s["sequence"]), "expected", (s.get("expected") or {}).get("value"))
        row("step", str(s["sequence"]), "actual", (s.get("actual") or {}).get("value"))
    row("disclaimer", "", "text", content["disclaimer"])
    return buf.getvalue()


def to_html(content: dict[str, Any]) -> str:
    """Print-ready HTML. Deliberately plain: it has to print legibly in a
    plant office and survive being photocopied."""
    s = content["session"]
    demo = content["project"].get("is_demo")

    def esc(v: Any) -> str:
        return (str(v) if v is not None else "—").replace("&", "&amp;").replace("<", "&lt;")

    rows = "".join(
        f"<tr><td>{esc(m['node'])}</td>"
        f"<td>{esc((m.get('expected') or {}).get('value'))}</td>"
        f"<td>{esc((m.get('measured') or {}).get('value'))}</td>"
        f"<td>{esc((m.get('measured') or {}).get('source'))}</td>"
        f"<td>{esc(m.get('status'))}</td></tr>"
        for m in content["measurements"]
    ) or "<tr><td colspan='5'>No measurements recorded.</td></tr>"

    findings = "".join(
        f"<li><strong>{esc(f.get('confidence'))}</strong> — {esc(f.get('statement'))}"
        f"<br><em>Recommended test:</em> {esc(f.get('recommended_test'))}</li>"
        for f in content["findings"]
    ) or "<li>No deterministic findings.</li>"

    steps = "".join(
        f"<tr><td>{esc(st['sequence'])}</td><td>{esc(st['title'])}<br>"
        f"<small>{esc(st['instruction'])}</small></td>"
        f"<td>{esc((st.get('expected') or {}).get('value'))}</td>"
        f"<td>{esc((st.get('actual') or {}).get('value'))}</td>"
        f"<td>{esc(st['status'])}</td></tr>"
        for st in content["steps"]
    ) or "<tr><td colspan='5'>No procedure generated.</td></tr>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{esc(s['title'])}</title>
<style>
 body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; color:#111; margin:32px; }}
 h1 {{ font-size:20px; margin:0 0 4px; }} h2 {{ font-size:14px; margin:24px 0 8px;
   text-transform:uppercase; letter-spacing:.08em; color:#444; border-bottom:1px solid #ccc; }}
 table {{ border-collapse:collapse; width:100%; font-size:12px; }}
 td,th {{ border:1px solid #bbb; padding:6px 8px; text-align:left; vertical-align:top; }}
 th {{ background:#eee; }}
 .demo {{ background:#7c2d12; color:#fff; padding:6px 10px; font-weight:700; margin-bottom:12px; }}
 .warn {{ border:2px solid #b45309; background:#fff7ed; padding:10px; font-size:12px;
   margin-top:24px; }}
 dl {{ display:grid; grid-template-columns:160px 1fr; gap:4px 12px; font-size:12px; }}
 dt {{ color:#555; }}
</style></head><body>
{'<div class="demo">DEMO MODE — SIMULATED DATA, NOT A REAL INSTALLATION</div>' if demo else ''}
<h1>{esc(s['title'])}</h1>
<div>Troubleshooting report — PowerTrace AI</div>
<h2>Header</h2>
<dl>
 <dt>Project</dt><dd>{esc(content['project']['name'])}</dd>
 <dt>Site / panel</dt><dd>{esc(content['project']['site'])} / {esc(content['project']['panel'])}</dd>
 <dt>Controller</dt><dd>{esc(content['controller']['name'])}
   {esc(content['controller']['manufacturer'])} {esc(content['controller']['model'])}</dd>
 <dt>Technician</dt><dd>{esc(s['technician'])}</dd>
 <dt>Opened</dt><dd>{esc(s['opened_at'])}</dd>
 <dt>Closed</dt><dd>{esc(s['closed_at'])}</dd>
 <dt>Fault</dt><dd>{esc(s['fault_category'])} — {esc(s['symptom'])}</dd>
</dl>
<h2>Measurements</h2>
<table><tr><th>Point</th><th>Expected</th><th>Measured</th><th>Source</th><th>Status</th></tr>
{rows}</table>
<h2>Diagnostic reasoning</h2><ul>{findings}</ul>
<h2>Procedure</h2>
<table><tr><th>#</th><th>Step</th><th>Expected</th><th>Actual</th><th>Status</th></tr>
{steps}</table>
<h2>Result</h2>
<p>{esc(s['resolution']) or 'Not recorded.'}</p>
<h2>Unresolved</h2>
<ul>{''.join(f'<li>{esc(u)}</li>' for u in s['unresolved_items']) or '<li>None recorded.</li>'}</ul>
<div class="warn">{esc(content['disclaimer'])}</div>
</body></html>"""


def to_pdf(content: dict[str, Any]) -> bytes | None:
    """Render with ReportLab if available; otherwise return None so the caller
    can fall back to HTML instead of shipping a broken PDF."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
    except ImportError:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=content["session"]["title"])
    styles = getSampleStyleSheet()
    flow: list[Any] = []
    if content["project"].get("is_demo"):
        flow.append(Paragraph("<b>DEMO MODE — SIMULATED DATA</b>", styles["Title"]))
    flow.append(Paragraph(content["session"]["title"], styles["Title"]))
    flow.append(Spacer(1, 10))
    for label, value in (
        ("Project", content["project"]["name"]),
        ("Controller", content["controller"]["name"]),
        ("Technician", content["session"]["technician"]),
        ("Opened", content["session"]["opened_at"]),
        ("Fault", content["session"]["fault_category"]),
    ):
        flow.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Measurements", styles["Heading2"]))
    table = [["Point", "Expected", "Measured", "Source", "Status"]] + [
        [m["node"], (m.get("expected") or {}).get("value", "—"),
         (m.get("measured") or {}).get("value", "—"),
         (m.get("measured") or {}).get("source", "—"), m.get("status", "—")]
        for m in content["measurements"]
    ]
    flow.append(Table(table))
    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Findings", styles["Heading2"]))
    for f in content["findings"]:
        flow.append(Paragraph(f"<b>{f.get('confidence')}</b> — {f.get('statement')}",
                              styles["Normal"]))
    flow.append(Spacer(1, 16))
    flow.append(Paragraph(content["disclaimer"], styles["Italic"]))
    doc.build(flow)
    return buf.getvalue()
