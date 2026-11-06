from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.schemas.admin import AdminCaseSearchParams, AdminFirmListParams, AdminLeadSearchParams
from app.schemas.case import CaseRead
from app.schemas.common import NumberedPage
from app.schemas.firm import FirmRead
from app.schemas.lead import LeadRead
from app.services import admin as admin_service

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
