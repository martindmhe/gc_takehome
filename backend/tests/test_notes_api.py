"""Firm-private case notes (against the seeded demo data).

Seed: California + employment routes to Firm A (Sarah, James). Emily is Firm B.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AuditEvent, CaseNote, Lead, LegalCase
from app.seed import seed
from tests.helpers import as_user, firm_id, submit_lead, user_by_email

ALICE = "alice@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
JAMES = "james@firm-a.example.com"  # Firm A paralegal
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


@pytest.fixture
def case(client: TestClient, db_session: Session) -> dict[str, Any]:
    """Alice's case, accepted by Firm A."""
    lead = submit_lead(client, as_user(db_session, ALICE))
    response = client.post(f"/api/leads/{lead['id']}/accept", headers=as_user(db_session, SARAH))
    assert response.status_code == 201, response.text
    return response.json()


def _notes_url(case: dict[str, Any]) -> str:
    return f"/api/cases/{case['id']}/notes"


def _add_note(client: TestClient, headers: dict[str, str], case: dict[str, Any], content: str) -> Any:
    return client.post(_notes_url(case), json={"content": content}, headers=headers)


def _reassign(db: Session, case: dict[str, Any], firm_pk: str) -> None:
    """Move the case (and its lead) to another firm. There's no API for this yet."""
    with db.begin():
        db.execute(
            update(LegalCase).where(LegalCase.id == uuid.UUID(case["id"])).values(assigned_firm_id=firm_pk)
        )
        db.execute(
            update(Lead).where(Lead.id == uuid.UUID(case["lead"]["id"])).values(assigned_firm_id=firm_pk)
        )


def test_firm_staff_can_add_and_read_their_notes(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    sarah, james = as_user(db_session, SARAH), as_user(db_session, JAMES)

    response = _add_note(client, sarah, case, "  Called the plaintiff; documents to follow.  ")
    assert response.status_code == 201, response.text
    note = response.json()
    assert note["content"] == "Called the plaintiff; documents to follow."
    assert note["author"]["display_name"] == user_by_email(db_session, SARAH).display_name
    assert note["owner_firm"]["id"] == firm_id(db_session, "Alder")

    # Paralegals have the same access as attorneys.
    assert _add_note(client, james, case, "Requested pay stubs.").status_code == 201
    page = client.get(_notes_url(case), headers=sarah).json()
    assert page["total"] == 2
    # Same timestamp inside the test transaction, so don't depend on the order here.
    assert {n["content"] for n in page["items"]} == {note["content"], "Requested pay stubs."}

    with db_session.begin():
        event = db_session.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(note["id"]))
        ).one()
    assert event.action == "note.created"
    assert "content" not in (event.new_values or {})


def test_blank_notes_are_rejected(client: TestClient, db_session: Session, case: dict[str, Any]) -> None:
    assert _add_note(client, as_user(db_session, SARAH), case, "   ").status_code == 422


def test_another_firm_cannot_read_or_add_notes(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    _add_note(client, as_user(db_session, SARAH), case, "Firm A strategy")
    emily = as_user(db_session, EMILY)

    assert client.get(_notes_url(case), headers=emily).status_code == 404
    assert _add_note(client, emily, case, "Firm B note").status_code == 404


def test_plaintiffs_cannot_access_notes(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    _add_note(client, as_user(db_session, SARAH), case, "Firm A strategy")
    alice = as_user(db_session, ALICE)

    assert client.get(_notes_url(case), headers=alice).status_code == 403
    assert _add_note(client, alice, case, "Let me in").status_code == 403

    # Notes aren't part of the plaintiff's case or document responses either.
    for url in (f"/api/cases/{case['id']}", f"/api/leads/{case['lead']['id']}/documents"):
        response = client.get(url, headers=alice)
        assert response.status_code == 200
        assert "Firm A strategy" not in response.text
        assert "notes" not in response.json()


def test_forged_owner_firm_is_rejected(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    sarah = as_user(db_session, SARAH)
    firm_b = firm_id(db_session, "Birchwood")

    for extra in ({"owner_firm_id": firm_b}, {"author_user_id": str(uuid.uuid4())}):
        response = client.post(
            _notes_url(case), json={"content": "Sneaky", **extra}, headers=sarah
        )
        assert response.status_code == 422

    with db_session.begin():
        assert db_session.scalars(select(CaseNote)).all() == []


def test_notes_keep_their_original_firm_after_reassignment(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    sarah, emily, admin = (as_user(db_session, e) for e in (SARAH, EMILY, ADMIN))
    firm_a, firm_b = firm_id(db_session, "Alder"), firm_id(db_session, "Birchwood")
    _add_note(client, sarah, case, "Firm A strategy")

    _reassign(db_session, case, firm_b)

    # The old firm loses access; the new firm sees none of the old firm's notes.
    assert client.get(_notes_url(case), headers=sarah).status_code == 404
    assert client.get(_notes_url(case), headers=emily).json()["total"] == 0
    assert _add_note(client, emily, case, "Firm B intake").status_code == 201
    assert [n["content"] for n in client.get(_notes_url(case), headers=emily).json()["items"]] == [
        "Firm B intake"
    ]

    # Admins still see which firm wrote each note.
    owners = {n["content"]: n["owner_firm"]["id"] for n in client.get(_notes_url(case), headers=admin).json()["items"]}
    assert owners == {"Firm A strategy": firm_a, "Firm B intake": firm_b}


def test_admins_can_read_but_not_add_notes(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    _add_note(client, as_user(db_session, SARAH), case, "Firm A strategy")
    admin = as_user(db_session, ADMIN)

    page = client.get(_notes_url(case), headers=admin).json()
    assert [n["content"] for n in page["items"]] == ["Firm A strategy"]
    assert page["items"][0]["owner_firm"]["name"] == "Alder & Associates (Firm A)"
    assert _add_note(client, admin, case, "Admin note").status_code == 403


def test_unknown_case_is_not_found(client: TestClient, db_session: Session) -> None:
    url = f"/api/cases/{uuid.uuid4()}/notes"
    assert client.get(url, headers=as_user(db_session, ADMIN)).status_code == 404
    assert client.post(url, json={"content": "x"}, headers=as_user(db_session, SARAH)).status_code == 404


def test_notes_are_paginated_newest_first(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    sarah_user = user_by_email(db_session, SARAH)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with db_session.begin():
        db_session.add_all(
            CaseNote(
                case_id=uuid.UUID(case["id"]),
                owner_firm_id=sarah_user.firm_id,
                author_user_id=sarah_user.id,
                content=f"Note {i}",
                created_at=start + timedelta(minutes=i),
            )
            for i in range(45)
        )

    sarah = as_user(db_session, SARAH)
    seen: list[str] = []
    for offset in (0, 20, 40):
        page = client.get(_notes_url(case), params={"limit": 20, "offset": offset}, headers=sarah).json()
        assert page["total"] == 45
        seen += [n["content"] for n in page["items"]]

    assert seen == [f"Note {i}" for i in reversed(range(45))]
    assert client.get(_notes_url(case), params={"limit": 101}, headers=sarah).status_code == 422
