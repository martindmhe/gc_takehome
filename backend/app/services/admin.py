"""Read-only admin search across every firm's leads and cases.

All filtering, counting, sorting and paging happens in SQL. Contact search uses
`ILIKE '%term%'`, which the pg_trgm GIN indexes on `leads.contact_name` and
`leads.contact_email` can serve without scanning every lead.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Firm, Lead, LegalCase, User
from app.models.enums import UserRole
from app.schemas.admin import AdminCaseSearchParams, AdminFirmListParams, AdminLeadSearchParams, SortOrder
from app.schemas.common import PageParams
from app.services.errors import ForbiddenError


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
