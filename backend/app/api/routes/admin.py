import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import AuditEvent, Lead, LegalCase
from app.schemas.admin import (
    AdminCaseSearchParams,
    AdminFirmListParams,
    AdminLeadSearchParams,
    AuditEventRead,
    FirmAssignment,
    HistoryParams,
)
from app.schemas.case import CaseRead
from app.schemas.common import NumberedPage
from app.schemas.firm import FirmRead
from app.schemas.lead import LeadRead
from app.schemas.user import UserSummary
from app.services import admin as admin_service
from app.services import cases as case_service
from app.services import leads as lead_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/leads", response_model=NumberedPage[LeadRead])
def search_leads(
    params: Annotated[AdminLeadSearchParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NumberedPage[LeadRead]:
    items, total = admin_service.search_leads(db, user, params)
    return NumberedPage(
        items=[LeadRead.model_validate(lead) for lead in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/cases", response_model=NumberedPage[CaseRead])
def search_cases(
    params: Annotated[AdminCaseSearchParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NumberedPage[CaseRead]:
    items, total = admin_service.search_cases(db, user, params)
    return NumberedPage(
        items=[CaseRead.model_validate(case) for case in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/firms", response_model=NumberedPage[FirmRead])
def list_firms(
    params: Annotated[AdminFirmListParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NumberedPage[FirmRead]:
    items, total = admin_service.list_firms(db, user, params)
    return NumberedPage(
        items=[FirmRead.model_validate(firm) for firm in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/leads/{lead_id}/assign", response_model=LeadRead)
def assign_lead(
    lead_id: uuid.UUID, data: FirmAssignment, user: CurrentUser, db: Session = Depends(get_db)
) -> Lead:
    admin_service.assign_lead(db, user, lead_id, data.firm_id)
    return lead_service.get_lead(db, user, lead_id)


@router.post("/cases/{case_id}/reassign", response_model=CaseRead)
def reassign_case(
    case_id: uuid.UUID, data: FirmAssignment, user: CurrentUser, db: Session = Depends(get_db)
) -> LegalCase:
    admin_service.reassign_case(db, user, case_id, data.firm_id)
    return case_service.get_case(db, user, case_id)


def _history_page(
    entries: list[tuple[AuditEvent, str]], total: int, params: HistoryParams
) -> NumberedPage[AuditEventRead]:
    return NumberedPage(
        items=[
            AuditEventRead(
                id=event.id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                action=event.action,
                actor=UserSummary.model_validate(event.actor) if event.actor else None,
                description=description,
                old_values=event.old_values,
                new_values=event.new_values,
                created_at=event.created_at,
            )
            for event, description in entries
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/leads/{lead_id}/history", response_model=NumberedPage[AuditEventRead])
def lead_history(
    lead_id: uuid.UUID,
    params: Annotated[HistoryParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NumberedPage[AuditEventRead]:
    return _history_page(*admin_service.lead_history(db, user, lead_id, params), params)


@router.get("/cases/{case_id}/history", response_model=NumberedPage[AuditEventRead])
def case_history(
    case_id: uuid.UUID,
    params: Annotated[HistoryParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NumberedPage[AuditEventRead]:
    return _history_page(*admin_service.case_history(db, user, case_id, params), params)
