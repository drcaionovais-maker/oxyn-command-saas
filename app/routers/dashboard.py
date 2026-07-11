from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user, tenant_object_or_404
from app.models import Alert, AlertLevel, Hospital, OperatingRoom, RoomStatus, SafetyChecklist, Shift, User
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Painel operacional"])


@router.get("/{hospital_id}", response_model=DashboardSummary)
def summary(hospital_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_object_or_404(db, Hospital, hospital_id, user.tenant_id)
    room_counts = db.execute(
        select(
            func.count(OperatingRoom.id),
            func.sum(case((OperatingRoom.status == RoomStatus.surgery, 1), else_=0)),
            func.sum(case((OperatingRoom.status.in_([RoomStatus.preparation, RoomStatus.recovery]), 1), else_=0)),
        ).where(OperatingRoom.tenant_id == user.tenant_id, OperatingRoom.hospital_id == hospital_id)
    ).one()
    alert_counts = db.execute(
        select(
            func.count(Alert.id),
            func.sum(case((Alert.level == AlertLevel.critical, 1), else_=0)),
        ).where(Alert.tenant_id == user.tenant_id, Alert.hospital_id == hospital_id, Alert.resolved_at.is_(None))
    ).one()
    active_staff = db.scalar(
        select(func.count(Shift.id)).where(
            Shift.tenant_id == user.tenant_id,
            Shift.hospital_id == hospital_id,
            Shift.shift_date == date.today(),
            Shift.check_in_at.is_not(None),
            Shift.check_out_at.is_(None),
        )
    ) or 0
    compliance = db.execute(
        select(
            func.count(SafetyChecklist.id),
            func.sum(case((SafetyChecklist.completed_at.is_not(None), 1), else_=0)),
        ).join(OperatingRoom, OperatingRoom.id == SafetyChecklist.room_id).where(
            SafetyChecklist.tenant_id == user.tenant_id, OperatingRoom.hospital_id == hospital_id
        )
    ).one()
    total_checklists, complete_checklists = compliance
    percent = round((complete_checklists or 0) * 100 / total_checklists, 1) if total_checklists else 100.0
    return DashboardSummary(
        hospital_id=hospital_id,
        rooms_total=room_counts[0] or 0,
        rooms_in_surgery=room_counts[1] or 0,
        rooms_in_transition=room_counts[2] or 0,
        active_staff=active_staff,
        open_alerts=alert_counts[0] or 0,
        critical_alerts=alert_counts[1] or 0,
        checklist_compliance_percent=percent,
    )
