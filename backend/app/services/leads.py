import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Firm, Lead, RoutingRule, User
from app.models.enums import FIRM_STAFF_ROLES, LeadStatus, UserRole
from app.schemas.lead import LeadCreate
from app.services.audit import record_event
from app.services.errors import ForbiddenError, NotFoundError


def _visible_leads(user: User) -> Select[tuple[Lead]]:
    """Leads the caller may see, as SQL. Every lead read starts here."""
    stmt = select(Lead).options(joinedload(Lead.assigned_firm))
    if user.role == UserRole.PLAINTIFF:
        return stmt.where(Lead.plaintiff_id == user.id)
    if user.role in FIRM_STAFF_ROLES:
        return stmt.where(Lead.assigned_firm_id == user.firm_id)
    if user.role == UserRole.ADMIN:
        return stmt
    raise ForbiddenError("Unknown role")


def create_lead(db: Session, user: User, data: LeadCreate) -> Lead:
    """Submit a lead for the signed-in plaintiff and route it, in one transaction."""
    if user.role != UserRole.PLAINTIFF:
        raise ForbiddenError("Only plaintiffs can submit leads")

    with db.begin():
        # (region, category) is unique in routing_rules, so this matches at most one firm.
        firm = db.scalar(
            select(Firm)
            .join(RoutingRule, RoutingRule.firm_id == Firm.id)
            .where(RoutingRule.region == data.region, RoutingRule.category == data.category)
        )
        lead = Lead(
            plaintiff_id=user.id,
            contact_name=data.contact_name,
            contact_email=data.contact_email,
            region=data.region,
            category=data.category,
            description=data.description,
            status=LeadStatus.ASSIGNED if firm else LeadStatus.PENDING_ASSIGNMENT,
            assigned_firm=firm,
        )
        db.add(lead)
        db.flush()

        record_event(
            db,
            entity_type="lead",
            entity_id=lead.id,
            action="lead.submitted",
            actor=user,
            new_values={"region": lead.region, "category": lead.category},
        )
        record_event(
            db,
            entity_type="lead",
            entity_id=lead.id,
            action="lead.routed",
            actor=None,  # SYSTEM
            new_values={
                "status": lead.status.value,
                "assigned_firm_id": str(firm.id) if firm else None,
            },
        )
    return lead


def list_leads(
    db: Session, user: User, *, status: LeadStatus | None, limit: int, offset: int
) -> tuple[Sequence[Lead], int]:
    """A newest-first page of the caller's visible leads, plus the total count."""
    stmt = _visible_leads(user)
    if status is not None:
        stmt = stmt.where(Lead.status == status)

    with db.begin():
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(
            stmt.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit).offset(offset)
        ).all()
    return items, total


def get_lead(db: Session, user: User, lead_id: uuid.UUID) -> Lead:
    with db.begin():
        lead = db.scalar(_visible_leads(user).where(Lead.id == lead_id))
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead
