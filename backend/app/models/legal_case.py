import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CaseStatus, case_status_type
from app.models.firm import Firm
from app.models.lead import Lead


class LegalCase(Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_firm_status_created", "assigned_firm_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # unique: a lead can produce at most one case.
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), unique=True)
    assigned_firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id"))
    status: Mapped[CaseStatus] = mapped_column(case_status_type, default=CaseStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    lead: Mapped[Lead] = relationship(back_populates="case", lazy="raise")
    assigned_firm: Mapped[Firm] = relationship(lazy="raise")
