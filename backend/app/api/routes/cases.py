import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import LegalCase
from app.schemas.case import CaseListParams, CaseRead, CaseStatusUpdate
from app.schemas.common import Page
from app.services import cases as case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=Page[CaseRead])
def list_cases(
    params: Annotated[CaseListParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Page[CaseRead]:
    items, total = case_service.list_cases(db, user, params)
    return Page(
        items=[CaseRead.model_validate(case) for case in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> LegalCase:
    return case_service.get_case(db, user, case_id)


@router.patch("/{case_id}/status", response_model=CaseRead)
def update_case_status(
    case_id: uuid.UUID, data: CaseStatusUpdate, user: CurrentUser, db: Session = Depends(get_db)
) -> LegalCase:
    case_service.update_case_status(db, user, case_id, data.status)
    return case_service.get_case(db, user, case_id)
