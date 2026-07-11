from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AlertLevel, Role, RoomStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
    role: Role = Role.viewer
    crm: str | None = None


class UserOut(ORMModel):
    id: str
    tenant_id: str
    email: str
    full_name: str
    role: Role
    crm: str | None
    active: bool


class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    city: str | None = None
    timezone: str = "America/Sao_Paulo"


class HospitalOut(ORMModel):
    id: str
    name: str
    city: str | None
    timezone: str
    active: bool


class RoomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    specialty: str | None = None


class RoomUpdate(BaseModel):
    status: RoomStatus | None = None
    specialty: str | None = None
    current_procedure: str | None = None
    started_at: datetime | None = None
    expected_end_at: datetime | None = None


class RoomOut(ORMModel):
    id: str
    hospital_id: str
    code: str
    name: str
    status: RoomStatus
    specialty: str | None
    current_procedure: str | None
    started_at: datetime | None
    expected_end_at: datetime | None


class ShiftCreate(BaseModel):
    hospital_id: str
    user_id: str
    room_id: str | None = None
    shift_date: date
    starts_at: datetime
    ends_at: datetime


class ShiftOut(ORMModel):
    id: str
    hospital_id: str
    user_id: str
    room_id: str | None
    shift_date: date
    starts_at: datetime
    ends_at: datetime
    check_in_at: datetime | None
    check_out_at: datetime | None


class ChecklistCreate(BaseModel):
    room_id: str
    patient_ref: str = Field(min_length=2, max_length=100)


class ChecklistUpdate(BaseModel):
    patient_identified: bool | None = None
    airway_plan_documented: bool | None = None
    antibiotics_confirmed: bool | None = None
    equipment_checked: bool | None = None
    postoperative_destination: bool | None = None


class ChecklistOut(ORMModel):
    id: str
    room_id: str
    patient_ref: str
    patient_identified: bool
    airway_plan_documented: bool
    antibiotics_confirmed: bool
    equipment_checked: bool
    postoperative_destination: bool
    completed_by_id: str | None
    completed_at: datetime | None


class AlertCreate(BaseModel):
    hospital_id: str | None = None
    room_id: str | None = None
    level: AlertLevel = AlertLevel.info
    title: str = Field(min_length=2, max_length=180)
    detail: str = Field(min_length=2, max_length=2000)


class AlertOut(ORMModel):
    id: str
    hospital_id: str | None
    room_id: str | None
    level: AlertLevel
    title: str
    detail: str
    resolved_at: datetime | None
    created_at: datetime


class DashboardSummary(BaseModel):
    hospital_id: str
    rooms_total: int
    rooms_in_surgery: int
    rooms_in_transition: int
    active_staff: int
    open_alerts: int
    critical_alerts: int
    checklist_compliance_percent: float
