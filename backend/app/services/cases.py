import uuid

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.orm import Session, joinedload

from app.models import Lead, LegalCase, User
from app.models.enums import FIRM_STAFF_ROLES, UserRole
from app.services.errors import ForbiddenError, NotFoundError


def _case_scope(user: User) -> ColumnElement[bool]:
    """SQL condition for the cases the caller may see (queries must join Lead)."""
    if user.role == UserRole.PLAINTIFF:
        return Lead.plaintiff_id == user.id
    if user.role in FIRM_STAFF_ROLES:
        return LegalCase.assigned_firm_id == user.firm_id
    if user.role == UserRole.ADMIN:
        return true()
    raise ForbiddenError("Unknown role")


def get_case(db: Session, user: User, case_id: uuid.UUID) -> LegalCase:
    stmt = (
        select(LegalCase)
        .join(Lead, Lead.id == LegalCase.lead_id)
        .where(LegalCase.id == case_id, _case_scope(user))
        .options(joinedload(LegalCase.lead), joinedload(LegalCase.assigned_firm))
    )
    with db.begin():
        case = db.scalar(stmt)
    if case is None:
        raise NotFoundError("Case not found")
    return case
