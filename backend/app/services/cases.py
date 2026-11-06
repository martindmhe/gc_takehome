import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, func, select, true, update
from sqlalchemy.orm import Session, joinedload

from app.models import Lead, LegalCase, User
from app.models.enums import FIRM_STAFF_ROLES, CaseStatus, UserRole
from app.schemas.case import CaseListParams
from app.services.audit import record_event
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _case_scope(user: User) -> ColumnElement[bool]:
    """SQL condition for the cases the caller may see (queries must join Lead)."""
    if user.role == UserRole.PLAINTIFF:
        return Lead.plaintiff_id == user.id
    if user.role in FIRM_STAFF_ROLES:
        return LegalCase.assigned_firm_id == user.firm_id
    if user.role == UserRole.ADMIN:
        return true()
    raise ForbiddenError("Unknown role")


def _visible_cases(user: User) -> Select[tuple[LegalCase]]:
    return (
        select(LegalCase)
        .join(Lead, Lead.id == LegalCase.lead_id)
        .where(_case_scope(user))
        .options(
            joinedload(LegalCase.lead).joinedload(Lead.plaintiff),
            joinedload(LegalCase.assigned_firm),
        )
    )


def list_cases(db: Session, user: User, params: CaseListParams) -> tuple[Sequence[LegalCase], int]:
    """A page of the caller's visible cases, newest first, plus the total count."""
    stmt = _visible_cases(user)
    if params.status is not None:
        stmt = stmt.where(LegalCase.status == params.status)

    with db.begin():
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(
            stmt.order_by(LegalCase.created_at.desc(), LegalCase.id.desc())
            .limit(params.limit)
            .offset(params.offset)
        ).all()
    return items, total


def get_case(db: Session, user: User, case_id: uuid.UUID) -> LegalCase:
    with db.begin():
        # populate_existing: refresh objects this session already holds (e.g. right
        # after update_case_status) instead of returning their stale attributes.
        case = db.scalar(
            _visible_cases(user)
            .where(LegalCase.id == case_id)
            .execution_options(populate_existing=True)
        )
    if case is None:
        raise NotFoundError("Case not found")
    return case


def update_case_status(db: Session, user: User, case_id: uuid.UUID, new_status: CaseStatus) -> None:
    """Set a case's progress status. Only staff of the currently assigned firm may do this.

    Setting the status it already has is a no-op: nothing is written or audited.
    """
    with db.begin():
        case = db.scalar(
            select(LegalCase)
            .join(Lead, Lead.id == LegalCase.lead_id)
            .where(LegalCase.id == case_id, _case_scope(user))
        )
        if case is None:
            raise NotFoundError("Case not found")
        if user.role not in FIRM_STAFF_ROLES:
            raise ForbiddenError("Only staff of the assigned firm can update case progress")
        old_status = case.status
        if old_status == new_status:
            return

        # Only applies if the case is still this firm's and still has the status we
        # read, so the audit's old value is right even if someone else just changed it.
        changed = db.scalar(
            update(LegalCase)
            .where(
                LegalCase.id == case.id,
                LegalCase.assigned_firm_id == user.firm_id,
                LegalCase.status == old_status,
            )
            .values(status=new_status)
            .returning(LegalCase.id)
        )
        if changed is None:
            raise ConflictError("This case was just updated by someone else. Reload and try again.")

        record_event(
            db,
            entity_type="case",
            entity_id=case.id,
            action="case.status_changed",
            actor=user,
            old_values={"status": old_status.value},
            new_values={"status": new_status.value},
        )
