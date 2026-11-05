import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole, user_role_type


class AuditEvent(Base):
    """Append-only history. Never updated or deleted.

    `actor_user_id` and `actor_role` are NULL for SYSTEM actions (e.g. routing).
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "(actor_user_id IS NULL) = (actor_role IS NULL)",
            name="ck_audit_events_actor_complete",
        ),
        Index("ix_audit_events_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID]
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[UserRole | None] = mapped_column(user_role_type)
    action: Mapped[str] = mapped_column(String(100))
    old_values: Mapped[dict[str, Any] | None]
    new_values: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
