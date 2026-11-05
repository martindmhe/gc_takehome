from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: User | None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an audit event in the caller's transaction. `actor=None` means SYSTEM."""
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(event)
    return event
