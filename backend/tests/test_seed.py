from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Firm, RoutingRule, User
from app.seed import FIRMS, ROUTING_RULES, USERS, seed


def _counts(db: Session) -> dict[str, int]:
    with db.begin():
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in (Firm, User, RoutingRule)
        }


def test_seed_is_idempotent(db_session: Session) -> None:
    seed(db_session)
    first = _counts(db_session)
    seed(db_session)

    assert _counts(db_session) == first == {
        "firms": len(FIRMS),
        "users": len(USERS),
        "routing_rules": len(ROUTING_RULES),
    }
