"""User, project and controller models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain import ConnectionState, DataType, Protocol, Role, WordOrder
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(20), default=Role.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Base, TimestampMixin):
    """A panel / site.  Everything else hangs off a project so a project can be
    duplicated wholesale for an identical panel."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    site: Mapped[str] = mapped_column(String(200), default="")
    panel: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # Nominal system data is entered by the user; nothing is assumed.
    nominal_voltage_v: Mapped[float | None] = mapped_column(Float)
    nominal_frequency_hz: Mapped[float | None] = mapped_column(Float)
    control_voltage_v: Mapped[float | None] = mapped_column(Float)

    controllers: Mapped[list["Controller"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Controller(Base, TimestampMixin):
    __tablename__ = "controllers"
    __table_args__ = (Index("ix_controllers_project_name", "project_id", "name", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    controller_type: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Live status, maintained by the poller.
    connection_state: Mapped[ConnectionState] = mapped_column(
        String(20), default=ConnectionState.OFFLINE, nullable=False
    )
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped[Project] = relationship(back_populates="controllers")
    protocol_config: Mapped["ProtocolConfiguration | None"] = relationship(
        back_populates="controller", cascade="all, delete-orphan", uselist=False
    )
    register_map: Mapped["RegisterMap | None"] = relationship()
    register_map_id: Mapped[int | None] = mapped_column(
        ForeignKey("register_maps.id", ondelete="SET NULL")
    )


class ProtocolConfiguration(Base, TimestampMixin):
    """Transport settings.  Kept separate from Controller so a second protocol
    (RTU, OPC UA) can be attached without reshaping the controller table."""

    __tablename__ = "protocol_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    controller_id: Mapped[int] = mapped_column(
        ForeignKey("controllers.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    protocol: Mapped[Protocol] = mapped_column(String(20), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    poll_interval_ms: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    timeout_s: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    # Serial / future transports and anything protocol-specific.
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    controller: Mapped[Controller] = relationship(back_populates="protocol_config")


class RegisterMap(Base, TimestampMixin):
    """A named, imported set of register definitions.

    PowerTrace AI ships no vendor register addresses.  A map must be imported
    from a document the user can cite, and it carries that citation plus a
    verified flag that the UI surfaces on every value derived from it.
    """

    __tablename__ = "register_maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    controller_type: Mapped[str] = mapped_column(String(120), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    # Free text: the document/revision the addresses were taken from.
    source_document: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_simulator_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    registers: Mapped[list["RegisterDefinition"]] = relationship(
        back_populates="register_map", cascade="all, delete-orphan"
    )


class RegisterDefinition(Base, TimestampMixin):
    __tablename__ = "register_definitions"
    __table_args__ = (
        UniqueConstraint("register_map_id", "parameter_name", name="uq_register_param"),
        Index("ix_register_addr", "register_map_id", "address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    register_map_id: Mapped[int] = mapped_column(
        ForeignKey("register_maps.id", ondelete="CASCADE"), nullable=False
    )
    controller_type: Mapped[str] = mapped_column(String(120), default="")
    parameter_name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[int] = mapped_column(Integer, nullable=False)
    function_code: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    data_type: Mapped[DataType] = mapped_column(String(16), default=DataType.UINT16, nullable=False)
    word_order: Mapped[WordOrder] = mapped_column(String(8), default=WordOrder.BIG, nullable=False)
    length: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    scale: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    offset: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    bit_position: Mapped[int | None] = mapped_column(Integer)
    read_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="")
    # Name in the normalized model, e.g. "voltage_L1_L2".  Empty means the
    # parameter is passed through as a raw named parameter only.
    normalized_key: Mapped[str] = mapped_column(String(120), default="", index=True)

    register_map: Mapped[RegisterMap] = relationship(back_populates="registers")


class Parameter(Base, TimestampMixin):
    """A normalized signal exposed to the frontend, decoupled from registers."""

    __tablename__ = "parameters"
    __table_args__ = (UniqueConstraint("controller_id", "key", name="uq_parameter_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    controller_id: Mapped[int] = mapped_column(
        ForeignKey("controllers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), default="")
    group: Mapped[str] = mapped_column(String(60), default="generator")
    unit: Mapped[str] = mapped_column(String(32), default="")
    # Engineering expectation for this signal, if the user has configured one.
    expected_min: Mapped[float | None] = mapped_column(Float)
    expected_max: Mapped[float | None] = mapped_column(Float)
