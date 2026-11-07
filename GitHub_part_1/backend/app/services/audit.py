from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None,
    *,
    ip_address: str | None = None,
    **details,
):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            details=details,
        )
    )
