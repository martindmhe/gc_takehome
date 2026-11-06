import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, func, or_, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import Firm, Lead, LegalCase, RoutingRule, User
from app.models.enums import FIRM_STAFF_ROLES, CaseStatus, LeadStatus, UserRole
from app.schemas.lead import LeadCreate, LeadListParams, LeadSort
from app.services.audit import record_event
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _lead_scope(user: User) -> ColumnElement[bool]:
    """SQL condition for the leads the caller may see. Every lead query uses it.

    Firm staff see only leads *currently* assigned to their firm, so a declined
    or reassigned lead disappears from the old firm immediately.
    """
    if user.role == UserRole.PLAINTIFF:
        return Lead.plaintiff_id == user.id
    if user.role in FIRM_STAFF_ROLES:
        return Lead.assigned_firm_id == user.firm_id
    if user.role == UserRole.ADMIN:
        return true()
    raise ForbiddenError("Unknown role")


def _visible_leads(user: User) -> Select[tuple[Lead]]:
    return (
        select(Lead)
        .where(_lead_scope(user))
        .options(joinedload(Lead.assigned_firm), joinedload(Lead.case))
    )


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
            case=None,
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


def list_leads(db: Session, user: User, params: LeadListParams) -> tuple[Sequence[Lead], int]:
    """A page of the caller's visible leads matching the filters, plus the total count."""
    stmt = _visible_leads(user)
    if params.status is not None:
        stmt = stmt.where(Lead.status == params.status)
    if params.category is not None:
        stmt = stmt.where(Lead.category == params.category)
    if params.region is not None:
        stmt = stmt.where(Lead.region == params.region)
    if params.created_from is not None:
        stmt = stmt.where(Lead.created_at >= params.created_from)
    if params.created_to is not None:
        stmt = stmt.where(Lead.created_at < params.created_to)
    if params.q is not None:
        stmt = stmt.where(
            or_(
                Lead.contact_name.icontains(params.q, autoescape=True),
                Lead.contact_email.icontains(params.q, autoescape=True),
                Lead.description.icontains(params.q, autoescape=True),
            )
        )

    if params.sort == LeadSort.OLDEST:
        order = (Lead.created_at.asc(), Lead.id.asc())
    else:
        order = (Lead.created_at.desc(), Lead.id.desc())

    with db.begin():
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.order_by(*order).limit(params.limit).offset(params.offset)).all()
    return items, total


def get_lead(db: Session, user: User, lead_id: uuid.UUID) -> Lead:
    with db.begin():
        lead = db.scalar(_visible_leads(user).where(Lead.id == lead_id))
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead

def accept_lead(db: Session, user: User, lead_id: uuid.UUID) -> uuid.UUID:
    """Accept an ASSIGNED lead for the caller's firm and open its case. Returns the case id."""
    try:
        with db.begin():
            lead = db.scalar(select(Lead).where(Lead.id == lead_id, _lead_scope(user)))
            if lead is None:
                raise NotFoundError("Lead not found")
            if user.role not in FIRM_STAFF_ROLES:
                raise ForbiddenError("Only staff of the assigned firm can accept or decline a lead")
            if lead.status != LeadStatus.ASSIGNED:
                raise ConflictError(
                    f"Only ASSIGNED leads can be accepted; this lead is {lead.status.value}"
                )

            # Only applies if the lead is still ASSIGNED to this firm at write time.
            # Postgres re-checks this WHERE after any concurrent update commits.
            changed = db.scalar(
                update(Lead)
                .where(
                    Lead.id == lead.id,
                    Lead.status == LeadStatus.ASSIGNED,
                    Lead.assigned_firm_id == user.firm_id,
                )
                .values(status=LeadStatus.ACCEPTED)
                .returning(Lead.id)
            )
            if changed is None:
                raise ConflictError("This lead has already been decided by someone else.")

            case = LegalCase(lead_id=lead.id, assigned_firm_id=user.firm_id, status=CaseStatus.OPEN)
            db.add(case)
            db.flush()

            record_event(
                db,
                entity_type="lead",
                entity_id=lead.id,
                action="lead.accepted",
                actor=user,
                old_values={"status": LeadStatus.ASSIGNED.value},
                new_values={"status": LeadStatus.ACCEPTED.value, "case_id": str(case.id)},
            )
            record_event(
                db,
                entity_type="case",
                entity_id=case.id,
                action="case.created",
                actor=user,
                new_values={
                    "lead_id": str(lead.id),
                    "assigned_firm_id": str(user.firm_id),
                    "status": CaseStatus.OPEN.value,
                },
            )
    except IntegrityError as exc:
        # Last-resort backstop: cases.lead_id is unique.
        if getattr(exc.orig.diag, "constraint_name", None) == "cases_lead_id_key":  # type: ignore[union-attr]
            raise ConflictError("A case already exists for this lead") from exc
        raise
    return case.id


def decline_lead(db: Session, user: User, lead_id: uuid.UUID) -> None:
    """Decline an ASSIGNED lead: it becomes DECLINED and unassigned, awaiting an admin."""
    with db.begin():
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, _lead_scope(user)))
        if lead is None:
            raise NotFoundError("Lead not found")
        if user.role not in FIRM_STAFF_ROLES:
            raise ForbiddenError("Only staff of the assigned firm can accept or decline a lead")
        if lead.status != LeadStatus.ASSIGNED:
            raise ConflictError(
                f"Only ASSIGNED leads can be declined; this lead is {lead.status.value}"
            )

        # Only applies if the lead is still ASSIGNED to this firm at write time.
        changed = db.scalar(
            update(Lead)
            .where(
                Lead.id == lead.id,
                Lead.status == LeadStatus.ASSIGNED,
                Lead.assigned_firm_id == user.firm_id,
            )
            .values(status=LeadStatus.DECLINED, assigned_firm_id=None)
            .returning(Lead.id)
        )
        if changed is None:
            raise ConflictError("This lead has already been decided by someone else.")

        record_event(
            db,
            entity_type="lead",
            entity_id=lead.id,
            action="lead.declined",
            actor=user,
            old_values={"status": LeadStatus.ASSIGNED.value, "assigned_firm_id": str(user.firm_id)},
            new_values={"status": LeadStatus.DECLINED.value, "assigned_firm_id": None},
        )
