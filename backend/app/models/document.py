import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    """PDF metadata. Documents belong to a lead; a case reaches them via its lead."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_lead_created", "lead_id", "created_at"),
        Index("ix_documents_uploaded_by_user_id", "uploaded_by_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # Path relative to STORAGE_DIR; never a client-supplied name.
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
