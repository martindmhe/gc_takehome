import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import LegalCase
from app.schemas.case import CaseRead
from app.services import cases as case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> LegalCase:
    return case_service.get_case(db, user, case_id)
