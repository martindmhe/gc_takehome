from collections.abc import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Firm
from app.schemas.firm import FirmRead
from app.services import firms as firm_service

router = APIRouter(prefix="/firms", tags=["firms"])


@router.get("", response_model=list[FirmRead])
def list_firms(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Sequence[Firm]:
    # response_model serializes the ORM objects through FirmRead.
    return firm_service.list_firms(db, limit=limit, offset=offset)
