from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import Category
from app.models.normalize import region_label
from app.schemas.common import Option
from app.schemas.meta import MetaResponse
from app.services import meta as meta_service

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
def get_meta(db: Session = Depends(get_db)) -> MetaResponse:
    return MetaResponse(
        categories=[Option(value=c.value, label=c.label) for c in Category],
        regions=[
            Option(value=r, label=region_label(r)) for r in meta_service.list_known_regions(db)
        ],
    )
