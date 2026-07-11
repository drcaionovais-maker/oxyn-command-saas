import json

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_action(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: str | None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str),
        )
    )
