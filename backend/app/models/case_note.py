import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.models.firm import Firm
from app.models.user import User


class CaseNote(Base):
    """Firm-private note. `owner_firm_id` is the authoring firm and never changes."""

    __tablename__ = "case_notes"
    __table_args__ = (
        Index("ix_case_notes_case_firm_created", "case_id", "owner_firm_id", "created_at"),
        Index("ix_case_notes_owner_firm_id", "owner_firm_id"),
        Index("ix_case_notes_author_user_id", "author_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    owner_firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id"))
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    author: Mapped[User] = relationship(lazy="raise")
    owner_firm: Mapped[Firm] = relationship(lazy="raise")

