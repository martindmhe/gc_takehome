import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import User


def list_demo_users(db: Session) -> Sequence[User]:
    """Every account, for the mock sign-in picker (demo data only)."""
    stmt = select(User).options(joinedload(User.firm)).order_by(User.role, User.display_name)
    with db.begin():
        return db.scalars(stmt).all()


def get_user(db: Session, user_id: uuid.UUID) -> User:
    with db.begin():
        return db.scalars(
            select(User).options(joinedload(User.firm)).where(User.id == user_id)
        ).one()
