from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.db.session import get_db
from app.models import User
from app.schemas.user import DemoUser
from app.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/demo-users", response_model=list[DemoUser])
def list_demo_users(db: Session = Depends(get_db)) -> Sequence[User]:
    """Accounts to pick from on the mock sign-in page."""
    return user_service.list_demo_users(db)


@router.get("/me", response_model=DemoUser)
def me(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    return user_service.get_user(db, user.id)
