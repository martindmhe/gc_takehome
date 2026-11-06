"""Helpers for API tests that run against the seeded demo data (`app.seed`)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.current_user import DEMO_USER_HEADER
from app.models import Firm, Lead, User


def user_by_email(db: Session, email: str) -> User:
    with db.begin():
        return db.scalars(select(User).where(User.email == email)).one()


def as_user(db: Session, email: str) -> dict[str, str]:
    """Request headers that mock-sign-in as the given seeded user."""
    return {DEMO_USER_HEADER: str(user_by_email(db, email).id)}


def firm_id(db: Session, name_prefix: str) -> str:
    with db.begin():
        return str(db.scalars(select(Firm.id).where(Firm.name.startswith(name_prefix))).one())


def lead_payload(**overrides: str) -> dict[str, str]:
    """A valid submission. California + employment routes to Firm A."""
    body = {
        "contact_name": "Alice Example",
        "contact_email": "alice@example.com",
        "region": "California",
        "category": "employment",
        "description": "I was let go after reporting a safety issue.",
    }
    body.update(overrides)
    return body


def submit_lead(client: TestClient, headers: dict[str, str], **overrides: str) -> dict[str, Any]:
    response = client.post("/api/leads", json=lead_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def set_created_at(db: Session, lead: dict[str, Any], when: datetime) -> None:
    with db.begin():
        db.execute(update(Lead).where(Lead.id == uuid.UUID(lead["id"])).values(created_at=when))


def space_out(db: Session, leads: list[dict[str, Any]]) -> None:
    """Give leads increasing created_at values, oldest first.

    Every test runs in one outer transaction, where Postgres now() is constant.
    """
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i, lead in enumerate(leads):
        set_created_at(db, lead, start + timedelta(minutes=i))
