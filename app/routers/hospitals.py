from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.dependencies import get_current_user, require_roles, tenant_object_or_404
from app.models import Hospital, OperatingRoom, Role, User
from app.schemas import HospitalCreate, HospitalOut, RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/hospitals", tags=["Hospitais e salas"])


@router.get("", response_model=list[HospitalOut])
def list_hospitals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Hospital).where(Hospital.tenant_id == user.tenant_id, Hospital.active.is_(True)).order_by(Hospital.name)
    ).all()


@router.post("", response_model=HospitalOut, status_code=201)
def create_hospital(
    body: HospitalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.owner, Role.admin)),
):
    exists = db.scalar(select(Hospital.id).where(Hospital.tenant_id == user.tenant_id, Hospital.name == body.name))
    if exists:
        raise HTTPException(status_code=409, detail="Hospital já cadastrado")
    hospital = Hospital(tenant_id=user.tenant_id, **body.model_dump())
    db.add(hospital)
    db.flush()
    log_action(db, user, "create", "hospital", hospital.id)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/{hospital_id}/rooms", response_model=list[RoomOut])
def list_rooms(hospital_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_object_or_404(db, Hospital, hospital_id, user.tenant_id)
    return db.scalars(
        select(OperatingRoom).where(
            OperatingRoom.tenant_id == user.tenant_id, OperatingRoom.hospital_id == hospital_id
        ).order_by(OperatingRoom.code)
    ).all()


@router.post("/{hospital_id}/rooms", response_model=RoomOut, status_code=201)
def create_room(
    hospital_id: str,
    body: RoomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.owner, Role.admin, Role.coordinator)),
):
    tenant_object_or_404(db, Hospital, hospital_id, user.tenant_id)
    exists = db.scalar(select(OperatingRoom.id).where(OperatingRoom.hospital_id == hospital_id, OperatingRoom.code == body.code))
    if exists:
        raise HTTPException(status_code=409, detail="Código de sala já cadastrado")
    room = OperatingRoom(tenant_id=user.tenant_id, hospital_id=hospital_id, **body.model_dump())
    db.add(room)
    db.flush()
    log_action(db, user, "create", "operating_room", room.id)
    db.commit()
    db.refresh(room)
    return room


@router.patch("/{hospital_id}/rooms/{room_id}", response_model=RoomOut)
def update_room(
    hospital_id: str,
    room_id: str,
    body: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.owner, Role.admin, Role.coordinator, Role.anesthetist, Role.nurse)),
):
    room = tenant_object_or_404(db, OperatingRoom, room_id, user.tenant_id)
    if room.hospital_id != hospital_id:
        raise HTTPException(status_code=404, detail="Sala não pertence ao hospital")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(room, key, value)
    log_action(db, user, "update", "operating_room", room.id, changes)
    db.commit()
    db.refresh(room)
    return room
