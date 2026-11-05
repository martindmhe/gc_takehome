"""Mock sign-in.

There are no passwords or tokens yet. The frontend lets you pick a seeded demo
account and sends its id in the `X-Demo-User-Id` header on every request. This
identifies the caller so services can apply role and scope checks; it is not a
security boundary. Swapping in real sign-in only changes this module.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User

DEMO_USER_HEADER = "X-Demo-User-Id"


def get_current_user(
    x_demo_user_id: Annotated[uuid.UUID | None, Header(alias=DEMO_USER_HEADER)] = None,
    db: Session = Depends(get_db),
) -> User:
    if x_demo_user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    # Close the read transaction so services can open their own with `db.begin()`.
    with db.begin():
        user = db.get(User, x_demo_user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown demo user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
