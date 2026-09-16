"""Dashboard, search, trends, reports and demo control."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ...domain import ConnectionState, Severity, utcnow
from ...models import (
    Alarm, Controller, DiagnosticSession, Project, Report, Schematic,
)
from ...protocols.simulator import FAULT_MODES, SimulatorAdapter
from ...schemas import ReportIn
from ...security import current_user, requires
from ...services import demo as demo_service
from ...services import reports as report_service
from ...services import search as search_service
from ...services.poller import polling_service
from ...services.value_store import store

router = APIRouter(prefix="/api", tags=["application"])


@router.get("/system/status")
def system_status(db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    controllers = list(db.scalars(select(Controller)))
    online = [c for c in controllers if c.connection_state == ConnectionState.ONLINE]
    offline = [c for c in controllers
               if c.connection_state in (ConnectionState.OFFLINE, ConnectionState.ERROR)]
    active_alarms = list(db.scalars(select(Alarm).where(Alarm.is_active.is_(True))))
    last_sync = max((c.last_ok_at for c in controllers if c.last_ok_at), default=None)

    return {
        "app": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "control_writes_enabled": settings.allow_control_writes,
        "server_time": utcnow().isoformat(),
        "controllers": {
            "total": len(controllers),
            "online": len(online),
            "offline": len(offline),
            "disabled": len([c for c in controllers
                             if c.connection_state == ConnectionState.DISABLED]),
            "simulated": len([c for c in controllers if c.is_simulated]),
            "polling": polling_service.active_ids,
        },
        "alarms": {
            "active": len(active_alarms),
            "shutdowns": len([a for a in active_alarms if a.severity == Severity.SHUTDOWN]),
            "warnings": len([a for a in active_alarms if a.severity == Severity.WARNING]),
            "unacknowledged": len([a for a in active_alarms if not a.acknowledged]),
        },
        "counts": {
            "projects": db.scalar(select(func.count()).select_from(Project)) or 0,
            "schematics": db.scalar(select(func.count()).select_from(Schematic)) or 0,
            "open_sessions": db.scalar(
                select(func.count()).select_from(DiagnosticSession)
                .where(DiagnosticSession.status == "OPEN")) or 0,
        },
        "last_synchronization": last_sync.isoformat() if last_sync else None,
        "safety": {
            "control_commands": "DISABLED — this application issues no control commands.",
            "notice": "Nothing here establishes that a circuit is de-energized.",
        },
    }


@router.get("/dashboard")
def dashboard(project_id: int | None = None, db: Session = Depends(get_db),
              _=Depends(current_user)) -> dict:
    stmt = select(Controller)
    if project_id:
        stmt = stmt.where(Controller.project_id == project_id)
    controllers = list(db.scalars(stmt))

    cards: list[dict] = []
    running = stopped = 0
    total_kw = 0.0
    voltages: list[float] = []
    frequencies: list[float] = []

    for c in controllers:
        values = store.latest(c.id)
        engine_status = (values.get("engine_status") or {}).get("value")
        kw = (values.get("kw") or {}).get("value")
        voltage = (values.get("voltage_L1_L2") or {}).get("value")
        frequency = (values.get("frequency") or {}).get("value")
        if engine_status == "RUNNING":
            running += 1
        elif engine_status is not None:
            stopped += 1
        if isinstance(kw, (int, float)):
            total_kw += kw
        if isinstance(voltage, (int, float)) and voltage > 0:
            voltages.append(voltage)
        if isinstance(frequency, (int, float)) and frequency > 0:
            frequencies.append(frequency)

        cards.append({
            "id": c.id, "project_id": c.project_id, "name": c.name,
            "manufacturer": c.manufacturer, "model": c.model,
            "connection_state": str(c.connection_state),
            "is_simulated": c.is_simulated,
            "host": c.protocol_config.host if c.protocol_config else None,
            "protocol": str(c.protocol_config.protocol) if c.protocol_config else None,
            "last_ok_at": c.last_ok_at.isoformat() if c.last_ok_at else None,
            "last_error": c.last_error,
            "values": {k: values.get(k) for k in
                       ("voltage_L1_L2", "frequency", "kw", "engine_status",
                        "breaker_status", "oil_pressure", "coolant_temperature")},
        })

    alarm_stmt = select(Alarm).where(Alarm.is_active.is_(True)).order_by(Alarm.raised_at.desc())
    if project_id:
        alarm_stmt = alarm_stmt.where(Alarm.project_id == project_id)
    alarms = list(db.scalars(alarm_stmt.limit(20)))

    # Aggregates are computed only from values that are actually present; a
    # missing controller lowers the count rather than being treated as zero.
    return {
        "controllers": cards,
        "summary": {
            "controllers_online": len([c for c in controllers
                                       if c.connection_state == ConnectionState.ONLINE]),
            "controllers_offline": len([c for c in controllers
                                        if c.connection_state in (ConnectionState.OFFLINE,
                                                                  ConnectionState.ERROR)]),
            "generators_running": running,
            "generators_stopped": stopped,
            "active_faults": len([a for a in alarms if a.severity in
                                  (Severity.SHUTDOWN, Severity.ALARM)]),
            "warnings": len([a for a in alarms if a.severity == Severity.WARNING]),
            "total_load_kw": round(total_kw, 1) if voltages else None,
            "system_voltage_v": round(sum(voltages) / len(voltages), 1) if voltages else None,
            "frequency_hz": round(sum(frequencies) / len(frequencies), 2)
            if frequencies else None,
            "contributing_controllers": len(voltages),
            "aggregate_note": (
                "Aggregates cover only controllers currently reporting. "
                f"{len(voltages)} of {len(controllers)} contributed."
            ),
        },
        "alarms": [{
            "id": a.id, "code": a.code, "description": a.description,
            "description_source": a.description_source,
            "severity": str(a.severity), "source": a.source,
            "raised_at": a.raised_at.isoformat(), "controller_id": a.controller_id,
            "acknowledged": a.acknowledged,
        } for a in alarms],
        "demo_mode": settings.demo_mode,
    }


@router.get("/search")
def global_search(q: str, project_id: int | None = None, db: Session = Depends(get_db),
                  _=Depends(current_user)) -> dict:
    results = search_service.search(db, q, project_id=project_id)
    return {"query": q, "count": len(results), "results": results}


@router.get("/trends")
def trends(controller_id: int, keys: str, seconds: float = Query(300.0, gt=0),
           _=Depends(current_user)) -> dict:
    requested = [k.strip() for k in keys.split(",") if k.strip()]
    return {
        "controller_id": controller_id,
        "window_s": seconds,
        "series": [{
            "key": key,
            "points": store.history(controller_id, key, seconds=seconds),
            "statistics": store.statistics(controller_id, key, seconds=seconds),
        } for key in requested],
        "note": "In-memory trend buffer; it does not survive a server restart.",
    }


@router.get("/trends/export")
def export_trends(controller_id: int, keys: str, seconds: float = Query(300.0, gt=0),
                  _=Depends(current_user)) -> Response:
    import csv
    import io

    requested = [k.strip() for k in keys.split(",") if k.strip()]
    series = {k: store.history(controller_id, k, seconds=seconds, max_points=10**6)
              for k in requested}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp_epoch", "key", "value"])
    for key, points in series.items():
        for point in points:
            writer.writerow([point["t"], key, point["v"]])
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="trend-{controller_id}.csv"'})


# --- Reports --------------------------------------------------------------
@router.get("/reports")
def list_reports(project_id: int | None = None, db: Session = Depends(get_db),
                 _=Depends(current_user)) -> list[dict]:
    stmt = select(Report).order_by(Report.generated_at.desc())
    if project_id:
        stmt = stmt.where(Report.project_id == project_id)
    return [{"id": r.id, "project_id": r.project_id, "title": r.title,
             "technician": r.technician, "generated_at": r.generated_at.isoformat(),
             "diagnostic_session_id": r.diagnostic_session_id} for r in db.scalars(stmt)]


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportIn, db: Session = Depends(get_db),
                  user=Depends(requires("report"))) -> dict:
    if not payload.diagnostic_session_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "a diagnostic session is required to build a report")
    session = db.get(DiagnosticSession, payload.diagnostic_session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")
    content = report_service.build_content(db, session)
    report = Report(
        project_id=session.project_id, diagnostic_session_id=session.id,
        title=payload.title or f"Troubleshooting report — {session.title}",
        technician=payload.technician or session.technician or user.email,
        generated_at=utcnow(), content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "title": report.title,
            "formats": {"json": f"/api/reports/{report.id}?format=json",
                        "csv": f"/api/reports/{report.id}?format=csv",
                        "html": f"/api/reports/{report.id}?format=html",
                        "pdf": f"/api/reports/{report.id}?format=pdf"}}


@router.get("/reports/{report_id}")
def get_report(report_id: int, format: str = Query("json", pattern="^(json|csv|html|pdf)$"),
               db: Session = Depends(get_db), _=Depends(current_user)) -> Response:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    content = report.content

    if format == "json":
        return Response(report_service.to_json(content), media_type="application/json")
    if format == "csv":
        return Response(report_service.to_csv(content), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}.csv"'})
    if format == "html":
        return Response(report_service.to_html(content), media_type="text/html")

    pdf = report_service.to_pdf(content)
    if pdf is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "PDF rendering needs ReportLab (pip install reportlab). "
            f"Use /api/reports/{report_id}?format=html and print to PDF in the meantime.",
        )
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'})


# --- Demo mode ------------------------------------------------------------
demo_router = APIRouter(prefix="/api/demo", tags=["demo"])


@demo_router.get("/status")
def demo_status(db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    return demo_service.status(db)


@demo_router.post("/seed")
async def seed_demo(reset: bool = False, db: Session = Depends(get_db),
                    _=Depends(requires("manage_projects"))) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "demo mode is disabled in this installation")
    project = demo_service.seed(db, reset=reset)
    for c in db.scalars(select(Controller).where(Controller.project_id == project.id)):
        await polling_service.ensure(c.id)
    return {"project_id": project.id, "name": project.name,
            "banner": "DEMO MODE — ALL VALUES SIMULATED"}


@demo_router.post("/fault")
def inject_fault(controller_id: int, mode: str, db: Session = Depends(get_db),
                 _=Depends(requires("diagnose"))) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "demo mode is disabled")
    controller = db.get(Controller, controller_id)
    if controller is None or not controller.is_simulated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulated controller not found")
    if mode not in FAULT_MODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"unknown fault mode; expected one of {FAULT_MODES}")
    adapter = SimulatorAdapter(key=f"controller-{controller_id}")
    adapter.set_fault(mode)
    return {"controller_id": controller_id, "fault_mode": mode,
            "note": "Simulated fault. All resulting values remain tagged SIMULATED."}


@demo_router.get("/faults")
def available_faults(_=Depends(current_user)) -> dict:
    return {"modes": FAULT_MODES}


@router.get("/settings")
def get_settings(_=Depends(current_user)) -> dict:
    """Read-only view of the running configuration."""
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "allow_control_writes": settings.allow_control_writes,
        "direct_input_voltage_limit_v": settings.direct_input_voltage_limit_v,
        "default_poll_interval_ms": settings.default_poll_interval_ms,
        "stale_after_s": settings.stale_after_s,
        "history_depth": settings.history_depth,
        "ai_provider": settings.ai_provider,
        "ai_model": settings.ai_model if settings.ai_provider != "none" else None,
        "database": settings.database_url.split("://")[0],
        "modbus_timeout_s": settings.modbus_timeout_s,
        "modbus_retries": settings.modbus_retries,
    }
