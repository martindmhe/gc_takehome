import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.models.normalize import normalize_region


class RoutingRule(Base):
    """Maps a (region, category) pair to the firm that receives matching leads."""

    __tablename__ = "routing_rules"
    __table_args__ = (
        CheckConstraint("region = lower(region)", name="ck_routing_rules_region_lowercase"),
        UniqueConstraint("region", "category", name="uq_routing_rules_region_category"),
        Index("ix_routing_rules_firm_id", "firm_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    region: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50))
    firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id"))

    @validates("region")
    def _normalize_region(self, _key: str, value: str) -> str:
        return normalize_region(value)
