import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uuid4() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    coordinator = "coordinator"
    anesthetist = "anesthetist"
    nurse = "nurse"
    viewer = "viewer"


class RoomStatus(str, enum.Enum):
    free = "free"
    preparation = "preparation"
    surgery = "surgery"
    recovery = "recovery"
    blocked = "blocked"


class AlertLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(30), default="professional")


class User(Base, TenantMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.viewer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    crm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class Hospital(Base, TenantMixin, TimestampMixin):
    __tablename__ = "hospitals"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_hospital_tenant_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), default="America/Sao_Paulo")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    rooms: Mapped[list["OperatingRoom"]] = relationship(back_populates="hospital", cascade="all, delete-orphan")


class OperatingRoom(Base, TenantMixin, TimestampMixin):
    __tablename__ = "operating_rooms"
    __table_args__ = (UniqueConstraint("hospital_id", "code", name="uq_room_hospital_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.free)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_procedure: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hospital: Mapped[Hospital] = relationship(back_populates="rooms")


class Shift(Base, TenantMixin, TimestampMixin):
    __tablename__ = "shifts"
    __table_args__ = (Index("ix_shift_tenant_day", "tenant_id", "shift_date"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("operating_rooms.id", ondelete="SET NULL"), nullable=True)
    shift_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SafetyChecklist(Base, TenantMixin, TimestampMixin):
    __tablename__ = "safety_checklists"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    room_id: Mapped[str] = mapped_column(ForeignKey("operating_rooms.id", ondelete="CASCADE"), index=True)
    patient_ref: Mapped[str] = mapped_column(String(100))
    patient_identified: Mapped[bool] = mapped_column(Boolean, default=False)
    airway_plan_documented: Mapped[bool] = mapped_column(Boolean, default=False)
    antibiotics_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    equipment_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    postoperative_destination: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Alert(Base, TenantMixin, TimestampMixin):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_tenant_open", "tenant_id", "resolved_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("operating_rooms.id", ondelete="SET NULL"), nullable=True)
    level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel), default=AlertLevel.info)
    title: Mapped[str] = mapped_column(String(180))
    detail: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AuditLog(Base, TenantMixin):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
