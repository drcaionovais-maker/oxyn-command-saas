from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.dependencies import get_current_user, tenant_object_or_404
from app.models import OperatingRoom, SafetyChecklist, User
from app.schemas import ChecklistCreate, ChecklistOut, ChecklistUpdate

router = APIRouter(prefix="/safety", tags=["Segurança do paciente"])

CHECK_FIELDS = (
    "patient_identified",
    "airway_plan_documented",
    "antibiotics_confirmed",
    "equipment_checked",
    "postoperative_destination",
)


@router.get("/checklists", response_model=list[ChecklistOut])
def list_checklists(room_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_object_or_404(db, OperatingRoom, room_id, user.tenant_id)
    return db.scalars(
        select(SafetyChecklist).where(
            SafetyChecklist.tenant_id == user.tenant_id, SafetyChecklist.room_id == room_id
        ).order_by(SafetyChecklist.created_at.desc())
    ).all()


@router.post("/checklists", response_model=ChecklistOut, status_code=201)
def create_checklist(
    body: ChecklistCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant_object_or_404(db, OperatingRoom, body.room_id, user.tenant_id)
    checklist = SafetyChecklist(tenant_id=user.tenant_id, **body.model_dump())
    db.add(checklist)
    db.flush()
    log_action(db, user, "create", "safety_checklist", checklist.id)
    db.commit()
    db.refresh(checklist)
    return checklist


@router.patch("/checklists/{checklist_id}", response_model=ChecklistOut)
def update_checklist(
    checklist_id: str,
    body: ChecklistUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    checklist = tenant_object_or_404(db, SafetyChecklist, checklist_id, user.tenant_id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(checklist, key, value)
    if all(getattr(checklist, field) for field in CHECK_FIELDS):
        checklist.completed_at = datetime.now(timezone.utc)
        checklist.completed_by_id = user.id
    else:
        checklist.completed_at = None
        checklist.completed_by_id = None
    log_action(db, user, "update", "safety_checklist", checklist.id, changes)
    db.commit()
    db.refresh(checklist)
    return checklist
