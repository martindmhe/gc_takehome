from sqlalchemy import Engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
