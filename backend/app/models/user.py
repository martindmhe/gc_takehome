import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole, user_role_type


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Firm staff belong to exactly one firm; plaintiffs and admins to none.
        CheckConstraint(
            "(role IN ('ATTORNEY', 'PARALEGAL')) = (firm_id IS NOT NULL)",
            name="ck_users_firm_staff_has_firm",
        ),
        Index("ix_users_firm_id", "firm_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200))
    # Stored lowercased by the application.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    role: Mapped[UserRole] = mapped_column(user_role_type)
    firm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("firms.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
