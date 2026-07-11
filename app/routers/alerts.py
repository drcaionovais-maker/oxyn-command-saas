from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.dependencies import get_current_user, tenant_object_or_404
from app.models import Alert, Hospital, OperatingRoom, User
from app.schemas import AlertCreate, AlertOut

router = APIRouter(prefix="/alerts", tags=["Alertas"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    hospital_id: str | None = None,
    open_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Alert).where(Alert.tenant_id == user.tenant_id)
    if hospital_id:
        tenant_object_or_404(db, Hospital, hospital_id, user.tenant_id)
        query = query.where(Alert.hospital_id == hospital_id)
    if open_only:
        query = query.where(Alert.resolved_at.is_(None))
    return db.scalars(query.order_by(Alert.created_at.desc())).all()


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(
    body: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.hospital_id:
        tenant_object_or_404(db, Hospital, body.hospital_id, user.tenant_id)
    if body.room_id:
        tenant_object_or_404(db, OperatingRoom, body.room_id, user.tenant_id)
    alert = Alert(tenant_id=user.tenant_id, **body.model_dump())
    db.add(alert)
    db.flush()
    log_action(db, user, "create", "alert", alert.id, {"level": body.level.value})
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = tenant_object_or_404(db, Alert, alert_id, user.tenant_id)
    if alert.resolved_at is not None:
        raise HTTPException(status_code=409, detail="Alerta já resolvido")
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by_id = user.id
    log_action(db, user, "resolve", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert
