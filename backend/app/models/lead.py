import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.models.normalize import normalize_region
from app.models.enums import LeadStatus, lead_status_type
from app.models.firm import Firm
from app.models.user import User


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("region = lower(region)", name="ck_leads_region_lowercase"),
        # ASSIGNED/ACCEPTED leads have a firm; PENDING_ASSIGNMENT/DECLINED never do.
        CheckConstraint(
            "(status IN ('ASSIGNED', 'ACCEPTED')) = (assigned_firm_id IS NOT NULL)",
            name="ck_leads_firm_matches_status",
        ),
        Index("ix_leads_plaintiff_created", "plaintiff_id", "created_at"),
        Index("ix_leads_firm_status_created", "assigned_firm_id", "status", "created_at"),
        Index("ix_leads_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plaintiff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    contact_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(320))
    region: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(lead_status_type)
    assigned_firm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("firms.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    plaintiff: Mapped[User] = relationship(lazy="raise")
    # lazy="raise": load it explicitly (joinedload) so list queries can't go N+1.
    assigned_firm: Mapped[Firm | None] = relationship(lazy="raise")
    # At most one (cases.lead_id is unique).
    case: Mapped["LegalCase | None"] = relationship(back_populates="lead", lazy="raise")

    @validates("region")
    def _normalize_region(self, _key: str, value: str) -> str:
        return normalize_region(value)
