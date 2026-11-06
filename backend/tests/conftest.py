"""PostgreSQL integration-test fixtures.

Tests run against a separate database (`<dev db name>_test`, or
`TEST_DATABASE_URL`), never the dev database. It is created if missing and its
schema is rebuilt once per test session. Each test runs inside a transaction
that is rolled back afterwards, so tests never see each other's data.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings, get_settings


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        url = make_url(explicit)
    else:
        dev = make_url(Settings().database_url)  # type: ignore[call-arg]
        url = dev.set(database=f"{dev.database}_test")
    if not (url.database or "").endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against non-test database {url.database!r}")
    return url.render_as_string(hide_password=False)


# Point the whole app (engine, settings) at the test database before it is imported.
TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.init_db import init_db  # noqa: E402
from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


def _ensure_database_exists(url: str) -> None:
    target = make_url(url)
    admin_engine = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin_engine.dispose()


def reset_schema() -> None:
    """Drop everything in the test database, leaving an empty public schema."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> Iterator[None]:
    _ensure_database_exists(TEST_DATABASE_URL)
    reset_schema()
    init_db(engine)
    yield
    engine.dispose()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session whose work is rolled back after the test.

    Code under test may use `with db.begin():` as usual; with
    `create_savepoint` those blocks become savepoints inside the outer
    transaction, and a failed block rolls back only its savepoint.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """API client whose requests share the test's rolled-back session."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
