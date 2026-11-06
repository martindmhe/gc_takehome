"""Firm inbox, lead inspection, and accept/decline (against the seeded demo data).

Seed: California + employment routes to Firm A (Sarah, James). Emily is Firm B.
"""

import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import AuditEvent, Firm, Lead, LegalCase, User
from app.models.enums import Category, LeadStatus, UserRole
from app.seed import seed
from app.services import leads as lead_service
from app.services.errors import ConflictError
from tests.helpers import as_user, firm_id, set_created_at, submit_lead, user_by_email

ALICE = "alice@example.com"
BOB = "bob@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
JAMES = "james@firm-a.example.com"  # Firm A paralegal
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


@pytest.fixture
def firm_a_lead(client: TestClient, db_session: Session) -> dict[str, Any]:
    """An ASSIGNED lead of Alice's, routed to Firm A."""
    lead = submit_lead(client, as_user(db_session, ALICE))
    assert lead["status"] == "ASSIGNED"
    return lead


def _cases_for(db: Session, lead_id: str) -> int:
    with db.begin():
        return db.scalar(
            select(func.count()).select_from(LegalCase).where(LegalCase.lead_id == uuid.UUID(lead_id))
        ) or 0


def _events(db: Session, entity_type: str, entity_id: str) -> dict[str, AuditEvent]:
    with db.begin():
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_type == entity_type, AuditEvent.entity_id == uuid.UUID(entity_id)
            )
        ).all()
    return {e.action: e for e in events}


# --- inbox -----------------------------------------------------------------------------


def test_inbox_shows_only_leads_assigned_to_the_callers_firm(
    client: TestClient, db_session: Session
) -> None:
    alice = as_user(db_session, ALICE)
    for_a = submit_lead(client, alice)
    submit_lead(client, alice, region="texas")  # Firm B
    submit_lead(client, alice, region="ohio")  # unmatched

    for email in (SARAH, JAMES):  # attorneys and paralegals see the same inbox
        page = client.get("/api/leads", headers=as_user(db_session, email)).json()
        assert [lead["id"] for lead in page["items"]] == [for_a["id"]]
        assert page["total"] == 1


def test_inbox_rejects_client_supplied_firm_id(client: TestClient, db_session: Session) -> None:
    response = client.get(
        "/api/leads",
        params={"firm_id": firm_id(db_session, "Birchwood")},
        headers=as_user(db_session, SARAH),
    )
    assert response.status_code == 422


def test_inbox_filters_in_sql(client: TestClient, db_session: Session) -> None:
    alice = as_user(db_session, ALICE)
    employment = submit_lead(client, alice, contact_name="Dana Rivers", description="fired")
    injury = submit_lead(client, alice, category="personal_injury", description="slipped on ice")
    new_york = submit_lead(client, alice, region="New York", category="personal_injury")
    set_created_at(db_session, employment, datetime(2026, 3, 1, tzinfo=UTC))
    set_created_at(db_session, injury, datetime(2026, 3, 15, tzinfo=UTC))
    set_created_at(db_session, new_york, datetime(2026, 4, 1, tzinfo=UTC))
    sarah = as_user(db_session, SARAH)

    def ids(**params: str) -> list[str]:
        response = client.get("/api/leads", params=params, headers=sarah)
        assert response.status_code == 200, response.text
        return [lead["id"] for lead in response.json()["items"]]

    assert ids(category="personal_injury") == [new_york["id"], injury["id"]]
    assert ids(region="  NEW york ") == [new_york["id"]]
    assert ids(q="RIVERS") == [employment["id"]]  # contact name, case-insensitive
    assert ids(q="SLIPPED") == [injury["id"]]  # description
    assert ids(created_from="2026-03-10T00:00:00Z", created_to="2026-04-01T00:00:00Z") == [
        injury["id"]
    ]
    assert ids(status="ASSIGNED", sort="oldest") == [employment["id"], injury["id"], new_york["id"]]


# --- accept ----------------------------------------------------------------------------


def test_correct_firm_can_accept_its_lead(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    response = client.post(
        f"/api/leads/{firm_a_lead['id']}/accept", headers=as_user(db_session, SARAH)
    )

    assert response.status_code == 201, response.text
    case = response.json()
    assert case["status"] == "OPEN"
    assert case["assigned_firm"]["id"] == firm_id(db_session, "Alder")
    assert case["lead"]["id"] == firm_a_lead["id"]

    lead = client.get(f"/api/leads/{firm_a_lead['id']}", headers=as_user(db_session, SARAH)).json()
    assert lead["status"] == "ACCEPTED"
    assert lead["case"] == {"id": case["id"], "status": "OPEN"}


def test_acceptance_creates_exactly_one_case_and_repeats_are_rejected(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    url = f"/api/leads/{firm_a_lead['id']}/accept"
    assert client.post(url, headers=as_user(db_session, SARAH)).status_code == 201

    again = client.post(url, headers=as_user(db_session, JAMES))

    assert again.status_code == 409
    assert "ACCEPTED" in again.json()["detail"]
    assert _cases_for(db_session, firm_a_lead["id"]) == 1


def test_another_firm_cannot_access_or_decide_on_the_lead(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    emily = as_user(db_session, EMILY)
    lead_url = f"/api/leads/{firm_a_lead['id']}"

    assert client.get(lead_url, headers=emily).status_code == 404
    assert client.post(f"{lead_url}/accept", headers=emily).status_code == 404
    assert client.post(f"{lead_url}/decline", headers=emily).status_code == 404
    assert client.get("/api/leads", headers=emily).json()["total"] == 0
    assert _cases_for(db_session, firm_a_lead["id"]) == 0


@pytest.mark.parametrize("email", [ALICE, ADMIN])
def test_only_firm_staff_can_decide(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any], email: str
) -> None:
    """Plaintiff and admin can see the lead but may not accept or decline it."""
    headers = as_user(db_session, email)
    for action in ("accept", "decline"):
        response = client.post(f"/api/leads/{firm_a_lead['id']}/{action}", headers=headers)
        assert response.status_code == 403, (email, action)


def test_accept_writes_audit_events(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    sarah = user_by_email(db_session, SARAH)
    case = client.post(
        f"/api/leads/{firm_a_lead['id']}/accept", headers=as_user(db_session, SARAH)
    ).json()

    accepted = _events(db_session, "lead", firm_a_lead["id"])["lead.accepted"]
    assert (accepted.actor_user_id, accepted.actor_role) == (sarah.id, UserRole.ATTORNEY)
    assert accepted.old_values == {"status": "ASSIGNED"}
    assert accepted.new_values == {"status": "ACCEPTED", "case_id": case["id"]}

    created = _events(db_session, "case", case["id"])
    assert set(created) == {"case.created"}
    assert created["case.created"].actor_user_id == sarah.id
    assert created["case.created"].new_values == {
        "lead_id": firm_a_lead["id"],
        "assigned_firm_id": firm_id(db_session, "Alder"),
        "status": "OPEN",
    }


# --- decline ---------------------------------------------------------------------------


def test_decline_unassigns_the_lead(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    response = client.post(
        f"/api/leads/{firm_a_lead['id']}/decline", headers=as_user(db_session, JAMES)
    )

    assert response.status_code == 200
    assert response.json() == {"id": firm_a_lead["id"], "status": "DECLINED"}
    with db_session.begin():
        lead = db_session.get(Lead, uuid.UUID(firm_a_lead["id"]))
        assert (lead.status, lead.assigned_firm_id) == (LeadStatus.DECLINED, None)

    # The plaintiff still sees it, now unassigned.
    mine = client.get(f"/api/leads/{firm_a_lead['id']}", headers=as_user(db_session, ALICE)).json()
    assert (mine["status"], mine["assigned_firm"]) == ("DECLINED", None)


def test_former_firm_loses_access_after_decline(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    sarah = as_user(db_session, SARAH)
    url = f"/api/leads/{firm_a_lead['id']}"
    client.post(f"{url}/decline", headers=sarah)

    assert client.get(url, headers=sarah).status_code == 404
    assert client.get("/api/leads", headers=sarah).json()["total"] == 0
    # Neither the old firm nor any other can accept it until an admin reassigns it.
    for email in (SARAH, EMILY):
        assert client.post(f"{url}/accept", headers=as_user(db_session, email)).status_code == 404
    assert _cases_for(db_session, firm_a_lead["id"]) == 0


def test_decline_writes_audit_event(
    client: TestClient, db_session: Session, firm_a_lead: dict[str, Any]
) -> None:
    james = user_by_email(db_session, JAMES)
    client.post(f"/api/leads/{firm_a_lead['id']}/decline", headers=as_user(db_session, JAMES))

    declined = _events(db_session, "lead", firm_a_lead["id"])["lead.declined"]
    assert (declined.actor_user_id, declined.actor_role) == (james.id, UserRole.PARALEGAL)
    assert declined.old_values == {
        "status": "ASSIGNED",
        "assigned_firm_id": firm_id(db_session, "Alder"),
    }
    assert declined.new_values == {"status": "DECLINED", "assigned_firm_id": None}


# --- concurrency -----------------------------------------------------------------------


@pytest.fixture
def committed_assigned_lead() -> Iterator[tuple[uuid.UUID, list[User]]]:
    """A really-committed ASSIGNED lead and two staff of its firm, cleaned up afterwards.

    The usual rolled-back `db_session` can't be shared across threads, so this
    test data is committed through separate connections.
    """
    with Session(engine, expire_on_commit=False) as db, db.begin():
        firm = Firm(name=f"Concurrency Firm {uuid.uuid4().hex[:6]}")
        db.add(firm)
        db.flush()
        tag = uuid.uuid4().hex
        plaintiff = User(display_name="P", email=f"p-{tag}@test.example.com", role=UserRole.PLAINTIFF)
        staff = [
            User(display_name=f"S{i}", email=f"s{i}-{tag}@test.example.com",
                 role=UserRole.ATTORNEY, firm_id=firm.id)
            for i in range(2)
        ]
        db.add_all([plaintiff, *staff])
        db.flush()
        lead = Lead(
            plaintiff_id=plaintiff.id, contact_name="P", contact_email="p@test.example.com",
            region="california", category=Category.EMPLOYMENT, description="race",
            status=LeadStatus.ASSIGNED, assigned_firm_id=firm.id,
        )
        db.add(lead)
        db.flush()
        ids = (lead.id, firm.id, [plaintiff.id, *(s.id for s in staff)])

    try:
        yield ids[0], staff
    finally:
        lead_id, firm_pk, user_ids = ids
        with Session(engine) as db, db.begin():
            case_ids = db.scalars(select(LegalCase.id).where(LegalCase.lead_id == lead_id)).all()
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_([lead_id, *case_ids])))
            db.execute(delete(LegalCase).where(LegalCase.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.execute(delete(Firm).where(Firm.id == firm_pk))


@pytest.fixture
def checks_pass_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make two concurrent decisions both pass their up-front checks before either writes.

    This forces the race the conditional UPDATE exists for; otherwise one thread
    usually finishes before the other starts and the ordinary checks catch it.
    """
    # The services build their guarded UPDATE right after the checks, so wait there.
    original_update = lead_service.update
    both_checked = threading.Barrier(2)

    def wait_then_update(*args: Any) -> Any:
        both_checked.wait(timeout=5)
        return original_update(*args)

    monkeypatch.setattr(lead_service, "update", wait_then_update)


def test_concurrent_acceptance_creates_one_case(
    committed_assigned_lead: tuple[uuid.UUID, list[User]], checks_pass_together: None
) -> None:
    lead_id, staff = committed_assigned_lead
    barrier = threading.Barrier(len(staff))
    results: list[object] = []

    def accept(user: User) -> None:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait()
            try:
                results.append(lead_service.accept_lead(db, user, lead_id))
            except Exception as exc:  # noqa: BLE001 - collected and asserted below
                results.append(exc)

    threads = [threading.Thread(target=accept, args=(user,)) for user in staff]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    successes = [r for r in results if isinstance(r, uuid.UUID)]
    conflicts = [r for r in results if isinstance(r, ConflictError) and "someone else" in str(r)]
    assert len(successes) == 1 and len(conflicts) == 1, results
    with Session(engine) as db:
        assert db.scalar(select(func.count()).where(LegalCase.lead_id == lead_id)) == 1
        assert db.get(Lead, lead_id).status == LeadStatus.ACCEPTED
