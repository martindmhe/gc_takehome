import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import Lead
from app.models.enums import LeadStatus
from app.schemas.common import Page
from app.schemas.lead import LeadCreate, LeadRead
from app.services import leads as lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(data: LeadCreate, user: CurrentUser, db: Session = Depends(get_db)) -> Lead:
    return lead_service.create_lead(db, user, data)


@router.get("", response_model=Page[LeadRead])
def list_leads(
    user: CurrentUser,
    status: LeadStatus | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[LeadRead]:
    items, total = lead_service.list_leads(db, user, status=status, limit=limit, offset=offset)
    return Page(
        items=[LeadRead.model_validate(lead) for lead in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> Lead:
    return lead_service.get_lead(db, user, lead_id)
