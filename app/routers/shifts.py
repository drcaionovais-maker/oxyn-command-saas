from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.dependencies import get_current_user, require_roles, tenant_object_or_404
from app.models import Hospital, OperatingRoom, Role, Shift, User
from app.schemas import ShiftCreate, ShiftOut

router = APIRouter(prefix="/shifts", tags=["Escalas e presença"])


@router.get("", response_model=list[ShiftOut])
def list_shifts(
    hospital_id: str,
    shift_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    tenant_object_or_404(db, Hospital, hospital_id, current.tenant_id)
    return db.scalars(
        select(Shift).where(
            Shift.tenant_id == current.tenant_id,
            Shift.hospital_id == hospital_id,
            Shift.shift_date == shift_date,
        ).order_by(Shift.starts_at)
    ).all()


@router.post("", response_model=ShiftOut, status_code=201)
def create_shift(
    body: ShiftCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(Role.owner, Role.admin, Role.coordinator)),
):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=422, detail="Término deve ser posterior ao início")
    tenant_object_or_404(db, Hospital, body.hospital_id, current.tenant_id)
    tenant_object_or_404(db, User, body.user_id, current.tenant_id)
    if body.room_id:
        tenant_object_or_404(db, OperatingRoom, body.room_id, current.tenant_id)
    shift = Shift(tenant_id=current.tenant_id, **body.model_dump())
    db.add(shift)
    db.flush()
    log_action(db, current, "create", "shift", shift.id)
    db.commit()
    db.refresh(shift)
    return shift


@router.post("/{shift_id}/check-in", response_model=ShiftOut)
def check_in(shift_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    shift = tenant_object_or_404(db, Shift, shift_id, current.tenant_id)
    if current.id != shift.user_id and current.role not in {Role.owner, Role.admin, Role.coordinator}:
        raise HTTPException(status_code=403, detail="Check-in não autorizado")
    shift.check_in_at = datetime.now(timezone.utc)
    log_action(db, current, "check_in", "shift", shift.id)
    db.commit()
    db.refresh(shift)
    return shift


@router.post("/{shift_id}/check-out", response_model=ShiftOut)
def check_out(shift_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    shift = tenant_object_or_404(db, Shift, shift_id, current.tenant_id)
    if current.id != shift.user_id and current.role not in {Role.owner, Role.admin, Role.coordinator}:
        raise HTTPException(status_code=403, detail="Check-out não autorizado")
    if not shift.check_in_at:
        raise HTTPException(status_code=409, detail="Faça o check-in primeiro")
    shift.check_out_at = datetime.now(timezone.utc)
    log_action(db, current, "check_out", "shift", shift.id)
    db.commit()
    db.refresh(shift)
    return shift
