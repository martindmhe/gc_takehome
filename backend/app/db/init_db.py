from sqlalchemy import Engine, text

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base


def init_db(engine: Engine) -> None:
    with engine.begin() as conn:
        # Trigram indexes for admin contact search (ships with PostgreSQL contrib).
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(engine)
