"""Alarm, event, diagnostic and report models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain import Severity
from .base import Base, TimestampMixin


class AlarmDefinition(Base, TimestampMixin):
    """User-imported alarm catalogue.

    No alarm code descriptions ship with the application.  A code with no
    imported definition is displayed as the raw code plus "NO DEFINITION
    IMPORTED" rather than a guessed description.
    """

    __tablename__ = "alarm_definitions"
    __table_args__ = (Index("ix_alarmdef_code", "catalogue", "code", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    catalogue: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[Severity] = mapped_column(String(16), default=Severity.ALARM)
    source_document: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")


class Alarm(Base, TimestampMixin):
    __tablename__ = "alarms"
    __table_args__ = (
        Index("ix_alarm_controller_active", "controller_id", "is_active"),
        Index("ix_alarm_raised", "raised_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    controller_id: Mapped[int | None] = mapped_column(
        ForeignKey("controllers.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(80), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # True when `description` came from an imported catalogue rather than the
    # controller itself or a placeholder.
    description_source: Mapped[str] = mapped_column(String(40), default="NONE")
    severity: Mapped[Severity] = mapped_column(String(16), default=Severity.ALARM, nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="CONTROLLER", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[str] = mapped_column(String(200), default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diagnostic_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Event(Base):
    """Timestamped record used for correlation: controller alarms, output
    transitions, measurements, connection changes."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_event_project_ts", "project_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    controller_id: Mapped[int | None] = mapped_column(
        ForeignKey("controllers.id", ondelete="SET NULL")
    )
    circuit_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuit_nodes.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(40), default="SYSTEM", nullable=False)
    code: Mapped[str] = mapped_column(String(80), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[Severity] = mapped_column(String(16), default=Severity.EVENT, nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="CONTROLLER", nullable=False)
    quality: Mapped[str] = mapped_column(String(16), default="GOOD", nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class TroubleshootingRule(Base, TimestampMixin):
    """A declarative diagnostic rule.

    Rules are data, not code, so an engineer can add a site-specific rule
    without a release.  Conditions are evaluated by the deterministic engine;
    the AI layer never edits rules.
    """

    __tablename__ = "troubleshooting_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fault_category: Mapped[str] = mapped_column(String(120), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    # {"all": [ {"kind": "controller_signal", "key": "...", "op": "==", "value": 1}, ...]}
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # {"finding": "...", "confidence": "LIKELY", "recommended_test": "...",
    #  "suspect_nodes": ["K12_CONTACT"]}
    conclusion: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(200), default="built-in")


class DiagnosticSession(Base, TimestampMixin):
    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    controller_id: Mapped[int | None] = mapped_column(
        ForeignKey("controllers.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    fault_category: Mapped[str] = mapped_column(String(120), default="", index=True)
    symptom: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="OPEN", nullable=False)
    technician: Mapped[str] = mapped_column(String(200), default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str] = mapped_column(Text, default="")
    unresolved_items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # Deterministic findings, kept distinct from the AI section.
    findings: Mapped[list[Any]] = mapped_column(JSON, default=list)
    ai_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    steps: Mapped[list["DiagnosticStep"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="DiagnosticStep.sequence"
    )


class DiagnosticStep(Base, TimestampMixin):
    __tablename__ = "diagnostic_steps"
    __table_args__ = (Index("ix_step_session_seq", "session_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, default="")
    # Everything a step shows is provenance-tagged.
    expected: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    actual: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    evidence: Mapped[list[Any]] = mapped_column(JSON, default=list)
    next_action: Mapped[str] = mapped_column(Text, default="")
    circuit_node_key: Mapped[str] = mapped_column(String(120), default="")
    requires_measurement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    safety_notice: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")

    session: Mapped[DiagnosticSession] = relationship(back_populates="steps")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    diagnostic_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    technician: Mapped[str] = mapped_column(String(200), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The report body is stored as structured JSON; renderers (PDF/CSV/JSON)
    # are views over it, so an export can be regenerated verbatim later.
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
