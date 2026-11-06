"""Case listing, details, and progress updates (against the seeded demo data).

Seed: California + employment routes to Firm A (Sarah, James). Emily is Firm B.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth.current_user import DEMO_USER_HEADER
from app.db.session import engine
from app.main import app
from app.models import AuditEvent, Firm, Lead, LegalCase, User
from app.models.enums import CaseStatus, UserRole
from app.seed import seed
from tests.factories import make_case, make_firm, make_lead, make_user
from tests.helpers import as_user, firm_id, submit_lead, user_by_email

ALICE = "alice@example.com"
BOB = "bob@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
JAMES = "james@firm-a.example.com"  # Firm A paralegal
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


def _open_case(client: TestClient, db: Session, plaintiff: str = ALICE, **lead: str) -> dict[str, Any]:
    """Submit a lead (routed to Firm A by default) and have Sarah accept it."""
    submitted = submit_lead(client, as_user(db, plaintiff), **lead)
    response = client.post(f"/api/leads/{submitted['id']}/accept", headers=as_user(db, SARAH))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def case(client: TestClient, db_session: Session) -> dict[str, Any]:
    """An OPEN case of Alice's, assigned to Firm A."""
    return _open_case(client, db_session)


def _set_status(client: TestClient, db: Session, case_id: str, email: str, status: str) -> Any:
    return client.patch(
        f"/api/cases/{case_id}/status", json={"status": status}, headers=as_user(db, email)
    )


def _status_events(db: Session, case_id: str) -> list[AuditEvent]:
    with db.begin():
        return list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(case_id),
                    AuditEvent.action == "case.status_changed",
                )
            )
        )


# --- reading ---------------------------------------------------------------------------


def test_plaintiff_sees_their_case_after_acceptance(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    alice = as_user(db_session, ALICE)

    page = client.get("/api/cases", headers=alice).json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == case["id"]

    detail = client.get(f"/api/cases/{case['id']}", headers=alice).json()
    assert detail["status"] == "OPEN"
    assert detail["assigned_firm"]["id"] == firm_id(db_session, "Alder")
    assert detail["lead"]["category_label"] == "Employment"
    assert detail["plaintiff"]["email"] == ALICE
    assert {"notes", "case_notes"}.isdisjoint(detail)


def test_plaintiff_cannot_see_another_plaintiffs_case(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    bob = as_user(db_session, BOB)

    assert client.get(f"/api/cases/{case['id']}", headers=bob).status_code == 404
    assert client.get("/api/cases", headers=bob).json()["total"] == 0


def test_list_is_scoped_to_the_callers_role(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    def ids(email: str) -> list[str]:
        return [c["id"] for c in client.get("/api/cases", headers=as_user(db_session, email)).json()["items"]]

    assert ids(SARAH) == ids(JAMES) == ids(ADMIN) == [case["id"]]
    assert ids(EMILY) == []


def test_list_filters_by_status_newest_first_and_paginates(
    client: TestClient, db_session: Session
) -> None:
    cases = [_open_case(client, db_session, description=f"case {i}") for i in range(3)]
    # now() is constant inside the test transaction, so give the cases distinct times.
    with db_session.begin():
        for i, c in enumerate(cases):
            db_session.execute(
                update(LegalCase)
                .where(LegalCase.id == uuid.UUID(c["id"]))
                .values(created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i))
            )
    _set_status(client, db_session, cases[0]["id"], SARAH, "IN_PROGRESS")
    sarah = as_user(db_session, SARAH)

    page = client.get("/api/cases", params={"limit": 2}, headers=sarah).json()
    assert page["total"] == 3
    assert [c["id"] for c in page["items"]] == [cases[2]["id"], cases[1]["id"]]

    page = client.get("/api/cases", params={"limit": 2, "offset": 2}, headers=sarah).json()
    assert [c["id"] for c in page["items"]] == [cases[0]["id"]]

    in_progress = client.get("/api/cases", params={"status": "IN_PROGRESS"}, headers=sarah).json()
    assert [c["id"] for c in in_progress["items"]] == [cases[0]["id"]]


def test_list_rejects_invalid_params(client: TestClient, db_session: Session) -> None:
    sarah = as_user(db_session, SARAH)
    for params in ({"status": "NOPE"}, {"limit": 101}, {"firm_id": str(uuid.uuid4())}):
        assert client.get("/api/cases", params=params, headers=sarah).status_code == 422, params


# --- progress updates ------------------------------------------------------------------


def test_assigned_staff_can_update_case_progress(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    response = _set_status(client, db_session, case["id"], SARAH, "IN_PROGRESS")
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"

    # Paralegals have the same permission.
    response = _set_status(client, db_session, case["id"], JAMES, "WAITING_ON_PLAINTIFF")
    assert response.json()["status"] == "WAITING_ON_PLAINTIFF"

    # The plaintiff sees the new progress.
    alice = as_user(db_session, ALICE)
    assert client.get(f"/api/cases/{case['id']}", headers=alice).json()["status"] == "WAITING_ON_PLAINTIFF"


def test_other_firms_cannot_read_or_update_the_case(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    emily = as_user(db_session, EMILY)

    assert client.get(f"/api/cases/{case['id']}", headers=emily).status_code == 404
    assert _set_status(client, db_session, case["id"], EMILY, "CLOSED").status_code == 404
    assert client.get(f"/api/cases/{case['id']}", headers=as_user(db_session, SARAH)).json()["status"] == "OPEN"


def test_plaintiff_and_admin_cannot_update_case_status(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    for email in (ALICE, ADMIN):
        assert _set_status(client, db_session, case["id"], email, "CLOSED").status_code == 403, email
    assert _status_events(db_session, case["id"]) == []


def test_only_defined_statuses_are_accepted(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    url = f"/api/cases/{case['id']}/status"
    sarah = as_user(db_session, SARAH)
    for body in ({"status": "DONE"}, {"status": "open"}, {}, {"status": "CLOSED", "lead_id": "x"}):
        assert client.patch(url, json=body, headers=sarah).status_code == 422, body


def test_unknown_case_is_not_found(client: TestClient, db_session: Session) -> None:
    assert _set_status(client, db_session, str(uuid.uuid4()), SARAH, "CLOSED").status_code == 404


def test_audit_history_captures_progress_changes(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    sarah = user_by_email(db_session, SARAH)
    _set_status(client, db_session, case["id"], SARAH, "IN_PROGRESS")
    _set_status(client, db_session, case["id"], SARAH, "CLOSED")

    events = _status_events(db_session, case["id"])
    changes = {(e.old_values["status"], e.new_values["status"]) for e in events}
    assert changes == {("OPEN", "IN_PROGRESS"), ("IN_PROGRESS", "CLOSED")}
    for event in events:
        assert event.entity_type == "case"
        assert (event.actor_user_id, event.actor_role) == (sarah.id, UserRole.ATTORNEY)
        assert event.created_at is not None


def test_setting_the_same_status_is_a_no_op(
    client: TestClient, db_session: Session, case: dict[str, Any]
) -> None:
    response = _set_status(client, db_session, case["id"], SARAH, "OPEN")

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"
    assert _status_events(db_session, case["id"]) == []


# --- persistence -------------------------------------------------------------------------


@pytest.fixture
def committed_case() -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    """A really-committed OPEN case and an attorney of its firm, cleaned up afterwards.

    The usual `db_session` is rolled back, so it can't show that a change survives
    beyond the request that made it.
    """
    with Session(engine, expire_on_commit=False) as db, db.begin():
        firm = make_firm(db, f"Persistence Firm {uuid.uuid4().hex[:6]}")
        plaintiff = make_user(db)
        attorney = make_user(db, UserRole.ATTORNEY, firm)
        lead = make_lead(db, plaintiff, firm)
        case = make_case(db, lead, firm)
        ids = (case.id, attorney.id, lead.id, [plaintiff.id, attorney.id], firm.id)

    try:
        yield ids[0], ids[1]
    finally:
        case_id, _, lead_id, user_ids, firm_pk = ids
        with Session(engine) as db, db.begin():
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id == case_id))
            db.execute(delete(LegalCase).where(LegalCase.id == case_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.execute(delete(Firm).where(Firm.id == firm_pk))


def test_status_updates_survive_a_reload(committed_case: tuple[uuid.UUID, uuid.UUID]) -> None:
    case_id, attorney_id = committed_case
    headers = {DEMO_USER_HEADER: str(attorney_id)}

    # A real app with real (committing) sessions, then a fresh one, as after a restart.
    with TestClient(app) as client:
        response = client.patch(f"/api/cases/{case_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
        assert response.status_code == 200, response.text
    with TestClient(app) as client:
        assert client.get(f"/api/cases/{case_id}", headers=headers).json()["status"] == "IN_PROGRESS"

    with Session(engine) as db:
        assert db.get(LegalCase, case_id).status == CaseStatus.IN_PROGRESS  # type: ignore[union-attr]
        event = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == case_id)).one()
        assert (event.action, event.actor_user_id) == ("case.status_changed", attorney_id)
