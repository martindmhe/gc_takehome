from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Firm


def list_firms(db: Session, *, limit: int, offset: int) -> Sequence[Firm]:
    # later restrict to perms 
    with db.begin():
        return db.scalars(
            select(Firm).order_by(Firm.name, Firm.id).limit(limit).offset(offset)
        ).all()
