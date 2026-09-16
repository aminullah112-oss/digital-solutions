from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import utcnow
from ...models import DiagnosticSession, DiagnosticStep, Project
from ...schemas import DiagnosticSessionIn, DiagnosticSessionOut, SessionUpdate, StepUpdate
from ...security import current_user, requires
from ...services import ai as ai_service
from ...services import circuit_graph as cg
from ...services import diagnostics as engine
from ...services import fault_tree

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/evaluate/{project_id}")
def evaluate(project_id: int, fault_category: str | None = None,
             db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    """Run the deterministic engine without opening a session."""
    if db.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    evidence = engine.build_evidence(db, project_id)
    result = engine.evaluate(db, project_id, fault_category=fault_category, evidence=evidence)
    result["fault_tree"] = fault_tree.build(
        fault_category or "BREAKER_FAIL_TO_CLOSE", evidence, result["discontinuities"]
    )
    return result


@router.get("/fault-tree/{project_id}")
def get_fault_tree(project_id: int, fault_category: str = "BREAKER_FAIL_TO_CLOSE",
                   db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    evidence = engine.build_evidence(db, project_id)
    result = engine.evaluate(db, project_id, fault_category=fault_category, evidence=evidence)
    return fault_tree.build(fault_category, evidence, result["discontinuities"])


@router.get("", response_model=list[DiagnosticSessionOut])
def list_sessions(project_id: int | None = None, limit: int = Query(50, le=500),
                  db: Session = Depends(get_db),
                  _=Depends(current_user)) -> list[DiagnosticSession]:
    stmt = (select(DiagnosticSession).order_by(DiagnosticSession.opened_at.desc()).limit(limit))
    if project_id:
        stmt = stmt.where(DiagnosticSession.project_id == project_id)
    return list(db.scalars(stmt))


@router.post("", response_model=DiagnosticSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: DiagnosticSessionIn, db: Session = Depends(get_db),
                   user=Depends(requires("diagnose"))) -> DiagnosticSession:
    """Open a diagnostic session.

    Order of work: assemble evidence, run deterministic rules, generate the
    procedure, and only then — if asked — hand the finished package to the AI
    layer.
    """
    if db.get(Project, payload.project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")

    session = DiagnosticSession(
        project_id=payload.project_id, controller_id=payload.controller_id,
        title=payload.title, fault_category=payload.fault_category, symptom=payload.symptom,
        technician=payload.technician or user.email, status="OPEN", opened_at=utcnow(),
    )
    db.add(session)
    db.flush()

    evidence = engine.build_evidence(db, payload.project_id)
    deterministic = engine.evaluate(db, payload.project_id,
                                    fault_category=payload.fault_category, evidence=evidence)
    session.findings = deterministic["findings"]

    snapshot = {k: v for k, v in evidence.items() if not k.startswith("_")}
    if payload.start_node_key:
        graph: cg.Graph = evidence["_graph"]
        if payload.start_node_key in graph.nodes:
            snapshot["trace"] = cg.highlight_circuit(graph, payload.start_node_key)
    snapshot["discontinuities"] = deterministic["discontinuities"]
    snapshot["coverage"] = deterministic["coverage"]
    session.evidence_snapshot = snapshot

    engine.generate_procedure(db, session, evidence)

    if payload.run_ai:
        session.ai_analysis = ai_service.analyze(
            evidence, deterministic,
            {"title": session.title, "fault_category": session.fault_category,
             "symptom": session.symptom},
        )

    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=DiagnosticSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db),
                _=Depends(current_user)) -> DiagnosticSession:
    session = db.get(DiagnosticSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")
    return session


@router.get("/{session_id}/fault-tree")
def session_fault_tree(session_id: int, db: Session = Depends(get_db),
                       _=Depends(current_user)) -> dict:
    session = db.get(DiagnosticSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")
    evidence = engine.build_evidence(db, session.project_id)
    result = engine.evaluate(db, session.project_id, fault_category=session.fault_category,
                             evidence=evidence)
    return fault_tree.build(session.fault_category, evidence, result["discontinuities"])


@router.post("/{session_id}/refresh", response_model=DiagnosticSessionOut)
def refresh_session(session_id: int, db: Session = Depends(get_db),
                    _=Depends(requires("diagnose"))) -> DiagnosticSession:
    """Re-run the deterministic engine against current data.

    Used after taking measurements: steps that were PENDING become PASS or
    FAIL once a measurement exists for their point.
    """
    session = db.get(DiagnosticSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")

    evidence = engine.build_evidence(db, session.project_id)
    deterministic = engine.evaluate(db, session.project_id,
                                    fault_category=session.fault_category, evidence=evidence)
    session.findings = deterministic["findings"]
    snapshot = {k: v for k, v in evidence.items() if not k.startswith("_")}
    snapshot["discontinuities"] = deterministic["discontinuities"]
    snapshot["coverage"] = deterministic["coverage"]
    session.evidence_snapshot = snapshot

    statuses = evidence["node_status"]
    for step in session.steps:
        if not step.circuit_node_key:
            continue
        status_row = statuses.get(step.circuit_node_key)
        if not status_row:
            continue
        step.expected = status_row.get("expected")
        step.actual = status_row.get("measured")
        step.status = engine._step_status(step.expected, step.actual)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/ai")
def run_ai(session_id: int, db: Session = Depends(get_db),
           _=Depends(requires("diagnose"))) -> dict:
    session = db.get(DiagnosticSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")
    evidence = engine.build_evidence(db, session.project_id)
    deterministic = engine.evaluate(db, session.project_id,
                                    fault_category=session.fault_category, evidence=evidence)
    analysis = ai_service.analyze(
        evidence, deterministic,
        {"title": session.title, "fault_category": session.fault_category,
         "symptom": session.symptom},
    )
    session.ai_analysis = analysis
    db.commit()
    return analysis


@router.patch("/{session_id}", response_model=DiagnosticSessionOut)
def update_session(session_id: int, payload: SessionUpdate, db: Session = Depends(get_db),
                   _=Depends(requires("diagnose"))) -> DiagnosticSession:
    session = db.get(DiagnosticSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic session not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(session, key, value)
    if data.get("status") in ("RESOLVED", "CLOSED"):
        session.closed_at = utcnow()
    db.commit()
    db.refresh(session)
    return session


@router.patch("/steps/{step_id}")
def update_step(step_id: int, payload: StepUpdate, db: Session = Depends(get_db),
                _=Depends(requires("diagnose"))) -> dict:
    step = db.get(DiagnosticStep, step_id)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "step not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(step, key, value)
    if data.get("status") in ("PASS", "FAIL", "SKIPPED"):
        step.completed_at = utcnow()
    db.commit()
    return {"id": step.id, "status": step.status, "notes": step.notes}


@router.get("/rules/list")
def list_rules(project_id: int | None = None, db: Session = Depends(get_db),
               _=Depends(current_user)) -> list[dict]:
    return engine.load_rules(db, project_id or 0)
