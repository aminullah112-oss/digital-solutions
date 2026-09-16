"""Schematic, circuit-graph and measurement models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain import EdgeType, NodeType
from .base import Base, TimestampMixin


class Schematic(Base, TimestampMixin):
    __tablename__ = "schematics"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    drawing_number: Mapped[str] = mapped_column(String(120), default="")
    revision: Mapped[str] = mapped_column(String(40), default="")
    original_filename: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    # The original file is always kept and is the authority; extraction output
    # is a derived, reviewable artifact.
    storage_path: Mapped[str] = mapped_column(String(500), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_status: Mapped[str] = mapped_column(String(40), default="UPLOADED", nullable=False)
    import_log: Mapped[list[Any]] = mapped_column(JSON, default=list)

    pages: Mapped[list["SchematicPage"]] = relationship(
        back_populates="schematic", cascade="all, delete-orphan"
    )


class SchematicPage(Base, TimestampMixin):
    __tablename__ = "schematic_pages"
    __table_args__ = (UniqueConstraint("schematic_id", "page_number", name="uq_page"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schematic_id: Mapped[int] = mapped_column(
        ForeignKey("schematics.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    width: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    render_path: Mapped[str] = mapped_column(String(500), default="")
    # Raw OCR/text extraction output, retained so a reviewer can see what the
    # importer actually read rather than only its conclusions.
    extracted_text: Mapped[list[Any]] = mapped_column(JSON, default=list)

    schematic: Mapped[Schematic] = relationship(back_populates="pages")


class Component(Base, TimestampMixin):
    """A physical device: relay, fuse, breaker, contactor, sensor, ..."""

    __tablename__ = "components"
    __table_args__ = (
        Index("ix_component_ref", "project_id", "reference_designator"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    schematic_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("schematic_pages.id", ondelete="SET NULL")
    )
    reference_designator: Mapped[str] = mapped_column(String(80), nullable=False)
    component_type: Mapped[NodeType] = mapped_column(String(32), default=NodeType.UNKNOWN)
    description: Mapped[str] = mapped_column(Text, default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    part_number: Mapped[str] = mapped_column(String(160), default="")
    rating: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    # 0..1, how confident the importer is that this component was read
    # correctly.  User-entered components are 1.0 and flagged verified.
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Terminal(Base, TimestampMixin):
    __tablename__ = "terminals"
    __table_args__ = (
        UniqueConstraint("project_id", "tag", name="uq_terminal_tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("components.id", ondelete="SET NULL")
    )
    # e.g. "TB23-14"
    tag: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    block: Mapped[str] = mapped_column(String(80), default="")
    number: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # Engineering expectation for this terminal, entered or imported, never
    # guessed from controller state.
    expected_voltage_v: Mapped[float | None] = mapped_column(Float)
    expected_reference: Mapped[str] = mapped_column(String(80), default="")  # e.g. "0V_RETURN"
    expected_tolerance_pct: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    expected_signal_type: Mapped[str] = mapped_column(String(20), default="DC")  # DC | AC | SIGNAL
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Wire(Base, TimestampMixin):
    __tablename__ = "wires"
    __table_args__ = (UniqueConstraint("project_id", "wire_number", name="uq_wire_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    wire_number: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(40), default="")
    gauge: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Connection(Base, TimestampMixin):
    """A reviewed physical connection between two endpoints, as read from the
    drawing.  Separate from CircuitEdge: this is the as-drawn record, the edge
    is the traversable graph representation."""

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    wire_id: Mapped[int | None] = mapped_column(ForeignKey("wires.id", ondelete="SET NULL"))
    from_terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminals.id", ondelete="CASCADE")
    )
    to_terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminals.id", ondelete="CASCADE")
    )
    schematic_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("schematic_pages.id", ondelete="SET NULL")
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class CircuitNode(Base, TimestampMixin):
    """Traversable graph node."""

    __tablename__ = "circuit_nodes"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_node_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    node_type: Mapped[NodeType] = mapped_column(String(32), default=NodeType.UNKNOWN, nullable=False)
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("components.id", ondelete="SET NULL")
    )
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminals.id", ondelete="SET NULL")
    )
    wire_id: Mapped[int | None] = mapped_column(ForeignKey("wires.id", ondelete="SET NULL"))
    schematic_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("schematic_pages.id", ondelete="SET NULL")
    )
    # Association to a controller signal, e.g. EMCP DO-07 -> parameter key.
    controller_id: Mapped[int | None] = mapped_column(
        ForeignKey("controllers.id", ondelete="SET NULL")
    )
    controller_signal: Mapped[str] = mapped_column(String(120), default="", index=True)
    # Nominal voltage of the circuit this node sits in, used for MV warnings.
    nominal_voltage_v: Mapped[float | None] = mapped_column(Float)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CircuitEdge(Base, TimestampMixin):
    __tablename__ = "circuit_edges"
    __table_args__ = (
        Index("ix_edge_from", "project_id", "from_node_id"),
        Index("ix_edge_to", "project_id", "to_node_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_node_id: Mapped[int] = mapped_column(
        ForeignKey("circuit_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[int] = mapped_column(
        ForeignKey("circuit_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[EdgeType] = mapped_column(
        String(24), default=EdgeType.CONNECTED_TO, nullable=False
    )
    wire_id: Mapped[int | None] = mapped_column(ForeignKey("wires.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(120), default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class MeasurementDevice(Base, TimestampMixin):
    """A physical measurement gateway.  Vendor-neutral by design."""

    __tablename__ = "measurement_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    transport: Mapped[str] = mapped_column(String(32), default="MODBUS_TCP")
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    connection_state: Mapped[str] = mapped_column(String(20), default="OFFLINE", nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    channels: Mapped[list["MeasurementChannel"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class MeasurementChannel(Base, TimestampMixin):
    """One input on a gateway, bound to a point in the circuit.

    The safety-relevant fields are mandatory at the API layer: an input cannot
    be bound to a point without declaring what it is rated for and whether the
    signal arrives through an isolating device.
    """

    __tablename__ = "measurement_channels"
    __table_args__ = (UniqueConstraint("device_id", "channel_tag", name="uq_channel_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_devices.id", ondelete="CASCADE"), nullable=False
    )
    channel_tag: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g. "AI-04"
    description: Mapped[str] = mapped_column(String(300), default="")
    input_type: Mapped[str] = mapped_column(String(24), default="VOLTAGE_DC", nullable=False)
    # Instrument limits.
    max_rated_input: Mapped[float | None] = mapped_column(Float)
    max_rated_input_unit: Mapped[str] = mapped_column(String(16), default="V")
    isolation_rating_v: Mapped[float | None] = mapped_column(Float)
    isolated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # PT / VT / CT / TRANSDUCER / DIRECT.  DIRECT is rejected above the
    # configured direct-input voltage limit.
    signal_conditioning: Mapped[str] = mapped_column(String(24), default="DIRECT", nullable=False)
    conditioning_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    conditioning_note: Mapped[str] = mapped_column(Text, default="")
    # Engineering scaling from raw counts to units.
    scale: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    offset: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="V")
    calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibration_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibration_reference: Mapped[str] = mapped_column(String(200), default="")
    # What this channel is physically clipped to.
    circuit_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuit_nodes.id", ondelete="SET NULL"), index=True
    )
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminals.id", ondelete="SET NULL"), index=True
    )
    nominal_circuit_voltage_v: Mapped[float | None] = mapped_column(Float)

    device: Mapped[MeasurementDevice] = relationship(back_populates="channels")


class Measurement(Base):
    """A physical measurement.  Source is always MEASURED or SIMULATED; it is
    never written by the controller poller."""

    __tablename__ = "measurements"
    __table_args__ = (
        Index("ix_measurement_node_ts", "circuit_node_id", "timestamp"),
        Index("ix_measurement_channel_ts", "channel_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("measurement_channels.id", ondelete="SET NULL")
    )
    circuit_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuit_nodes.id", ondelete="SET NULL")
    )
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminals.id", ondelete="SET NULL")
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="V", nullable=False)
    quality: Mapped[str] = mapped_column(String(16), default="GOOD", nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="MEASURED", nullable=False)
    method: Mapped[str] = mapped_column(String(40), default="GATEWAY")  # GATEWAY | MANUAL | SIM
    instrument: Mapped[str] = mapped_column(String(200), default="")
    technician: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    diagnostic_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
