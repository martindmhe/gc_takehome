"""Admin-only operations: search across every firm, assignment, and audit history.

Search: all filtering, counting, sorting and paging happens in SQL. Contact search uses
`ILIKE '%term%'`, which the pg_trgm GIN indexes on `leads.contact_name` and
`leads.contact_email` can serve without scanning every lead.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import AuditEvent, CaseNote, Document, Firm, Lead, LegalCase, User
from app.models.enums import Category, LeadStatus, UserRole
from app.models.normalize import region_label
from app.schemas.admin import (
    AdminCaseSearchParams,
    AdminFirmListParams,
    AdminLeadSearchParams,
    HistoryParams,
    SortOrder,
)
from app.schemas.common import PageParams
from app.services.audit import record_event
from app.services.errors import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError

# Leads in these states have no case yet, so an admin assigns them directly.
# ACCEPTED leads follow their case: reassign the case instead.
ASSIGNABLE_LEAD_STATUSES = frozenset(
    {LeadStatus.PENDING_ASSIGNMENT, LeadStatus.DECLINED, LeadStatus.ASSIGNED}
)


def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Only admins can use admin search")


def _contact_matches(q: str) -> ColumnElement[bool]:
    """Lead contact name or email contains `q`, case-insensitively.

    `q` is a bound parameter (never spliced into the SQL), and `%`, `_` and `\\`
    are escaped so they match literally instead of acting as wildcards.
    """
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        Lead.contact_name.ilike(pattern, escape="\\"),
        Lead.contact_email.ilike(pattern, escape="\\"),
    )


def _page(db: Session, stmt: Select[Any], order: Sequence[Any], params: PageParams) -> tuple[Sequence[Any], int]:
    with db.begin():
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        items = db.scalars(stmt.order_by(*order).limit(params.page_size).offset(params.offset)).all()
    return items, total


def search_leads(db: Session, user: User, params: AdminLeadSearchParams) -> tuple[Sequence[Lead], int]:
    _require_admin(user)
    stmt = select(Lead).options(joinedload(Lead.assigned_firm), joinedload(Lead.case))
    if params.q is not None:
        stmt = stmt.where(_contact_matches(params.q))
    if params.status is not None:
        stmt = stmt.where(Lead.status == params.status)
    if params.category is not None:
        stmt = stmt.where(Lead.category == params.category)
    if params.region is not None:
        stmt = stmt.where(Lead.region == params.region)
    if params.firm_id is not None:
        stmt = stmt.where(Lead.assigned_firm_id == params.firm_id)

    if params.sort == SortOrder.OLDEST:
        order = (Lead.created_at.asc(), Lead.id.asc())
    else:
        order = (Lead.created_at.desc(), Lead.id.desc())
    return _page(db, stmt, order, params)


def search_cases(db: Session, user: User, params: AdminCaseSearchParams) -> tuple[Sequence[LegalCase], int]:
    _require_admin(user)
    stmt = (
        select(LegalCase)
        .join(Lead, Lead.id == LegalCase.lead_id)
        .options(
            joinedload(LegalCase.lead).joinedload(Lead.plaintiff),
            joinedload(LegalCase.assigned_firm),
        )
    )
    if params.q is not None:
        stmt = stmt.where(_contact_matches(params.q))
    if params.status is not None:
        stmt = stmt.where(LegalCase.status == params.status)
    if params.firm_id is not None:
        stmt = stmt.where(LegalCase.assigned_firm_id == params.firm_id)

    if params.sort == SortOrder.OLDEST:
        order = (LegalCase.created_at.asc(), LegalCase.id.asc())
    else:
        order = (LegalCase.created_at.desc(), LegalCase.id.desc())
    return _page(db, stmt, order, params)


def list_firms(db: Session, user: User, params: AdminFirmListParams) -> tuple[Sequence[Firm], int]:
    """Every firm by name, e.g. for the admin firm filter."""
    _require_admin(user)
    return _page(db, select(Firm), (Firm.name, Firm.id), params)


# --- assignment ---------------------------------------------------------------
#
# Access for firm staff is computed from `assigned_firm_id` on every request (see
# the `_scope` functions in leads/cases/documents/notes), so changing these columns
# is the whole reassignment: the old firm loses access and the new firm gains it
# on their next request. Notes keep their `owner_firm_id`, so they stay with the
# firm that wrote them.


def _target_firm(db: Session, firm_id: uuid.UUID) -> Firm:
    firm = db.get(Firm, firm_id)
    if firm is None:
        raise InvalidRequestError("Choose an existing firm")
    return firm


def assign_lead(db: Session, user: User, lead_id: uuid.UUID, firm_id: uuid.UUID) -> None:
    """Assign an unaccepted lead (pending, declined, or assigned) to a firm, making it ASSIGNED."""
    _require_admin(user)
    with db.begin():
        # FOR UPDATE: a concurrent accept/decline/assign of this lead waits for us,
        # then re-checks its own conditions against what we wrote.
        lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
        if lead is None:
            raise NotFoundError("Lead not found")
        if lead.status not in ASSIGNABLE_LEAD_STATUSES:
            raise ConflictError(
                "This lead has been accepted and has a case. Reassign the case instead; "
                "the lead moves with it."
            )
        firm = _target_firm(db, firm_id)
        if lead.status == LeadStatus.ASSIGNED and lead.assigned_firm_id == firm.id:
            raise ConflictError(f"This lead is already assigned to {firm.name}")

        old_values = {
            "status": lead.status.value,
            "assigned_firm_id": str(lead.assigned_firm_id) if lead.assigned_firm_id else None,
        }
        lead.status = LeadStatus.ASSIGNED
        lead.assigned_firm_id = firm.id
        record_event(
            db,
            entity_type="lead",
            entity_id=lead.id,
            action="lead.assigned",
            actor=user,
            old_values=old_values,
            new_values={"status": LeadStatus.ASSIGNED.value, "assigned_firm_id": str(firm.id)},
        )


def reassign_case(db: Session, user: User, case_id: uuid.UUID, firm_id: uuid.UUID) -> None:
    """Move a case, and its lead, to another firm. Progress status, documents and notes are untouched."""
    _require_admin(user)
    with db.begin():
        # Lock the case and its lead together, so a concurrent status update,
        # upload or note waits and then sees the new firm.
        row = db.execute(
            select(LegalCase, Lead)
            .join(Lead, Lead.id == LegalCase.lead_id)
            .where(LegalCase.id == case_id)
            .with_for_update()
        ).one_or_none()
        if row is None:
            raise NotFoundError("Case not found")
        case, lead = row
        firm = _target_firm(db, firm_id)
        if case.assigned_firm_id == firm.id:
            raise ConflictError(f"This case is already assigned to {firm.name}")

        old_firm_id = case.assigned_firm_id
        case.assigned_firm_id = firm.id
        lead.assigned_firm_id = firm.id  # the two never disagree (domain contract)

        change = {
            "old_values": {"assigned_firm_id": str(old_firm_id)},
            "new_values": {"assigned_firm_id": str(firm.id)},
        }
        record_event(
            db, entity_type="case", entity_id=case.id, action="case.reassigned", actor=user, **change
        )
        record_event(
            db,
            entity_type="lead",
            entity_id=lead.id,
            action="lead.reassigned",
            actor=user,
            old_values=change["old_values"],
            new_values={**change["new_values"], "case_id": str(case.id)},
        )


# --- audit history ---------------------------------------------------------------


def _events_for(entity_type: str, ids: Any) -> ColumnElement[bool]:
    """Events about one entity id, or about every id a subquery returns."""
    condition = AuditEvent.entity_id.in_(ids) if isinstance(ids, Select) else AuditEvent.entity_id == ids
    return and_(AuditEvent.entity_type == entity_type, condition)


def _lead_events(lead_id: uuid.UUID) -> ColumnElement[bool]:
    """The lead itself and its documents."""
    return or_(
        _events_for("lead", lead_id),
        _events_for("document", select(Document.id).where(Document.lead_id == lead_id)),
    )


def lead_history(
    db: Session, user: User, lead_id: uuid.UUID, params: HistoryParams
) -> tuple[list[tuple[AuditEvent, str]], int]:
    """The lead's audit trail, oldest first. Includes case reassignments (logged on the lead too)."""
    _require_admin(user)
    with db.begin():
        if db.get(Lead, lead_id) is None:
            raise NotFoundError("Lead not found")
    return _history(db, _lead_events(lead_id), params)


def case_history(
    db: Session, user: User, case_id: uuid.UUID, params: HistoryParams
) -> tuple[list[tuple[AuditEvent, str]], int]:
    """The case's audit trail, oldest first: the case, its notes, and its lead's events."""
    _require_admin(user)
    with db.begin():
        case = db.get(LegalCase, case_id)
        if case is None:
            raise NotFoundError("Case not found")
        lead_id = case.lead_id
    condition = or_(
        _events_for("case", case_id),
        _events_for("case_note", select(CaseNote.id).where(CaseNote.case_id == case_id)),
        _lead_events(lead_id),
    )
    return _history(db, condition, params)


def _history(
    db: Session, condition: ColumnElement[bool], params: HistoryParams
) -> tuple[list[tuple[AuditEvent, str]], int]:
    stmt = select(AuditEvent).where(condition).options(joinedload(AuditEvent.actor))
    events, total = _page(db, stmt, (AuditEvent.created_at.asc(), AuditEvent.id.asc()), params)

    # One query for every firm the page mentions, so descriptions can name them.
    firm_ids = {
        uuid.UUID(value)
        for e in events
        for values in (e.old_values, e.new_values)
        for key, value in (values or {}).items()
        if key in ("assigned_firm_id", "owner_firm_id") and value
    }
    with db.begin():
        rows = db.execute(select(Firm.id, Firm.name).where(Firm.id.in_(firm_ids)))
        firm_names = {firm_pk: name for firm_pk, name in rows}
    return [(e, describe(e, firm_names)) for e in events], total


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def describe(event: AuditEvent, firm_names: dict[uuid.UUID, str]) -> str:
    # readable output from an event for tests/debug
    old, new = event.old_values or {}, event.new_values or {}

    def firm(values: dict[str, Any], key: str = "assigned_firm_id") -> str:
        value = values.get(key)
        return firm_names.get(uuid.UUID(value), "an unknown firm") if value else "no firm"

    match event.action:
        case "lead.submitted":
            category = new.get("category")
            label = Category(category).label if category in Category else category
            return f"Lead submitted ({label}, {region_label(new.get('region', ''))})"
        case "lead.routed":
            if new.get("assigned_firm_id"):
                return f"Automatically routed to {firm(new)}"
            return "No firm matched the category and region; waiting for an admin to assign one"
        case "lead.accepted":
            return "Lead accepted; case opened"
        case "lead.declined":
            return f"Declined by {firm(old)}; lead is unassigned"
        case "lead.assigned":
            was = _label(old.get("status", "")).lower()
            if old.get("assigned_firm_id"):
                return f"Lead reassigned from {firm(old)} to {firm(new)}"
            return f"Lead assigned to {firm(new)} (was {was})"
        case "lead.reassigned":
            return f"Lead moved from {firm(old)} to {firm(new)} with its case"
        case "case.created":
            return f"Case opened for {firm(new)}"
        case "case.status_changed":
            return f"Case status changed from {_label(old.get('status', ''))} to {_label(new.get('status', ''))}"
        case "case.reassigned":
            return f"Case reassigned from {firm(old)} to {firm(new)}"
        case "document.uploaded":
            return f"Uploaded {new.get('original_filename', 'a document')}"
        case "note.created":
            return f"Private note added for {firm(new, 'owner_firm_id')}"
        case _:
            return event.action
