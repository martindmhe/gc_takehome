import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import Lead, LegalCase
from app.models.enums import LeadStatus
from app.schemas.case import CaseRead
from app.schemas.common import Page
from app.schemas.lead import LeadCreate, LeadDeclined, LeadListParams, LeadRead
from app.services import cases as case_service
from app.services import leads as lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(data: LeadCreate, user: CurrentUser, db: Session = Depends(get_db)) -> Lead:
    return lead_service.create_lead(db, user, data)


@router.get("", response_model=Page[LeadRead])
def list_leads(
    params: Annotated[LeadListParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Page[LeadRead]:
    items, total = lead_service.list_leads(db, user, params)
    return Page(
        items=[LeadRead.model_validate(lead) for lead in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> Lead:
    return lead_service.get_lead(db, user, lead_id)


@router.post("/{lead_id}/accept", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def accept_lead(lead_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> LegalCase:
    # return the created case
    case_id = lead_service.accept_lead(db, user, lead_id)
    return case_service.get_case(db, user, case_id)


@router.post("/{lead_id}/decline", response_model=LeadDeclined)
def decline_lead(lead_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> LeadDeclined:
    lead_service.decline_lead(db, user, lead_id)
    return LeadDeclined(id=lead_id, status=LeadStatus.DECLINED)
