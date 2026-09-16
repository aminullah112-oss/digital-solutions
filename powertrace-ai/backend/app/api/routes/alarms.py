from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import utcnow
from ...models import Alarm, AlarmDefinition, Event
from ...schemas import AlarmDefinitionIn, AlarmOut
from ...security import current_user, requires
from ...services import correlation

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmOut])
def list_alarms(project_id: int | None = None, active_only: bool = False,
                limit: int = Query(200, le=2000), db: Session = Depends(get_db),
                _=Depends(current_user)) -> list[Alarm]:
    stmt = select(Alarm).order_by(Alarm.raised_at.desc()).limit(limit)
    if project_id:
        stmt = stmt.where(Alarm.project_id == project_id)
    if active_only:
        stmt = stmt.where(Alarm.is_active.is_(True))
    return list(db.scalars(stmt))


@router.post("/{alarm_id}/acknowledge", response_model=AlarmOut)
def acknowledge(alarm_id: int, db: Session = Depends(get_db),
                user=Depends(requires("diagnose"))) -> Alarm:
    alarm = db.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alarm not found")
    alarm.acknowledged = True
    alarm.acknowledged_by = user.email
    alarm.acknowledged_at = utcnow()
    db.commit()
    db.refresh(alarm)
    return alarm


@router.get("/events")
def list_events(project_id: int, minutes: float = Query(60.0, gt=0),
                limit: int = Query(500, le=5000), db: Session = Depends(get_db),
                _=Depends(current_user)) -> dict:
    since = utcnow() - timedelta(minutes=minutes)
    return {
        "project_id": project_id, "since": since.isoformat(),
        "events": correlation.timeline(db, project_id, since=since, limit=limit),
    }


@router.get("/correlate")
def correlate(project_id: int, at: str, window_s: float = Query(30.0, gt=0, le=3600),
              db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    from datetime import datetime

    try:
        anchor = datetime.fromisoformat(at)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "at must be an ISO-8601 timestamp") from None
    return correlation.correlate_around(db, project_id, anchor, window_s=window_s)


@router.get("/definitions")
def list_definitions(catalogue: str | None = None, db: Session = Depends(get_db),
                     _=Depends(current_user)) -> list[dict]:
    stmt = select(AlarmDefinition).order_by(AlarmDefinition.catalogue, AlarmDefinition.code)
    if catalogue:
        stmt = stmt.where(AlarmDefinition.catalogue == catalogue)
    return [{
        "id": d.id, "catalogue": d.catalogue, "code": d.code, "description": d.description,
        "severity": str(d.severity), "source_document": d.source_document,
        "recommended_action": d.recommended_action,
    } for d in db.scalars(stmt)]


@router.post("/definitions", status_code=status.HTTP_201_CREATED)
def import_definitions(payload: list[AlarmDefinitionIn], db: Session = Depends(get_db),
                       _=Depends(requires("configure_controllers"))) -> dict:
    """Import an alarm catalogue.

    No alarm descriptions ship with the application. Codes without an imported
    definition are shown as the raw code, never as a guessed description.
    """
    created = updated = 0
    for item in payload:
        existing = db.scalars(select(AlarmDefinition).where(
            AlarmDefinition.catalogue == item.catalogue,
            AlarmDefinition.code == item.code)).first()
        if existing:
            for key, value in item.model_dump().items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(AlarmDefinition(**item.model_dump()))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


@router.post("/resolve-descriptions")
def resolve_descriptions(project_id: int, catalogue: str, db: Session = Depends(get_db),
                         _=Depends(requires("configure_controllers"))) -> dict:
    """Backfill alarm descriptions from an imported catalogue."""
    definitions = {d.code: d for d in db.scalars(
        select(AlarmDefinition).where(AlarmDefinition.catalogue == catalogue))}
    resolved = 0
    for alarm in db.scalars(select(Alarm).where(Alarm.project_id == project_id)):
        definition = definitions.get(alarm.code)
        if definition and alarm.description_source != "CATALOGUE":
            alarm.description = definition.description
            alarm.description_source = "CATALOGUE"
            alarm.severity = definition.severity
            resolved += 1
    db.commit()
    return {"resolved": resolved, "catalogue": catalogue,
            "unresolved_note": "Codes with no catalogue entry keep their raw code."}
