"""Plaintiff lead submission, routing, and browsing (against the seeded demo data)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.current_user import DEMO_USER_HEADER
from app.models import AuditEvent, Lead
from app.seed import seed
from tests.helpers import as_user, firm_id, lead_payload, space_out, submit_lead, user_by_email


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


# --- routing -------------------------------------------------------------------------


def test_matching_lead_routes_to_exactly_one_firm(client: TestClient, db_session: Session) -> None:
    lead = submit_lead(client, as_user(db_session, "alice@example.com"))

    assert lead["status"] == "ASSIGNED"
    assert lead["assigned_firm"]["id"] == firm_id(db_session, "Alder")
    assert lead["region"] == "california"
    assert lead["region_label"] == "California"
    assert lead["category_label"] == "Employment"


def test_unmatched_lead_is_pending_assignment(client: TestClient, db_session: Session) -> None:
    alice = as_user(db_session, "alice@example.com")

    unmapped_combo = submit_lead(client, alice, region="florida", category="immigration")
    unknown_region = submit_lead(client, alice, region="Ohio")

    for lead in (unmapped_combo, unknown_region):
        assert lead["status"] == "PENDING_ASSIGNMENT"
        assert lead["assigned_firm"] is None


def test_routing_is_deterministic(client: TestClient, db_session: Session) -> None:
    alice = as_user(db_session, "alice@example.com")

    leads = [
        submit_lead(client, alice, region=region, category="family")
        for region in ("new york", "  New   York ", "NEW YORK")
    ]

    firm_b = firm_id(db_session, "Birchwood")
    assert {lead["region"] for lead in leads} == {"new york"}
    assert [lead["assigned_firm"]["id"] for lead in leads] == [firm_b] * 3


def test_audit_events_are_written(client: TestClient, db_session: Session) -> None:
    alice = user_by_email(db_session, "alice@example.com")
    lead = submit_lead(client, {DEMO_USER_HEADER: str(alice.id)})

    with db_session.begin():
        events = db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "lead", AuditEvent.entity_id == uuid.UUID(lead["id"]))
        ).all()

    by_action = {e.action: e for e in events}
    assert len(events) == 2
    assert set(by_action) == {"lead.submitted", "lead.routed"}

    assert by_action["lead.submitted"].actor_user_id == alice.id
    assert by_action["lead.submitted"].actor_role == "PLAINTIFF"

    routed = by_action["lead.routed"]
    assert routed.actor_user_id is None and routed.actor_role is None  # SYSTEM
    assert routed.new_values == {
        "status": "ASSIGNED",
        "assigned_firm_id": firm_id(db_session, "Alder"),
    }


# --- browsing and authorization ---------------------------------------------------------


def test_alice_can_list_and_inspect_her_leads(client: TestClient, db_session: Session) -> None:
    alice = as_user(db_session, "alice@example.com")
    first = submit_lead(client, alice, description="first")
    second = submit_lead(client, alice, description="second", region="ohio")
    submit_lead(client, as_user(db_session, "bob@example.com"), description="bob's")
    space_out(db_session, [first, second])

    page = client.get("/api/leads", headers=alice).json()
    assert page["total"] == 2
    assert page["limit"] == 25
    assert [lead["id"] for lead in page["items"]] == [second["id"], first["id"]]  # newest first

    detail = client.get(f"/api/leads/{first['id']}", headers=alice)
    assert detail.status_code == 200
    assert detail.json()["description"] == "first"
    assert "plaintiff_id" not in detail.json()


def test_bob_cannot_inspect_alices_leads(client: TestClient, db_session: Session) -> None:
    alice_lead = submit_lead(client, as_user(db_session, "alice@example.com"))
    bob = as_user(db_session, "bob@example.com")

    assert client.get(f"/api/leads/{alice_lead['id']}", headers=bob).status_code == 404
    assert client.get("/api/leads", headers=bob).json()["total"] == 0


def test_staff_cannot_submit_leads(client: TestClient, db_session: Session) -> None:
    for email in ("sarah@firm-a.example.com", "james@firm-a.example.com", "admin@example.com"):
        response = client.post("/api/leads", json=lead_payload(), headers=as_user(db_session, email))
        assert response.status_code == 403, email

    with db_session.begin():
        assert db_session.scalars(select(Lead)).all() == []


def test_client_cannot_supply_a_different_plaintiff_id(
    client: TestClient, db_session: Session
) -> None:
    alice = as_user(db_session, "alice@example.com")
    bob_id = str(user_by_email(db_session, "bob@example.com").id)

    response = client.post("/api/leads", json=lead_payload(plaintiff_id=bob_id), headers=alice)

    assert response.status_code == 422
    with db_session.begin():
        assert db_session.scalars(select(Lead)).all() == []


def test_requests_without_a_user_are_rejected(client: TestClient) -> None:
    assert client.post("/api/leads", json=lead_payload()).status_code == 401
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads", headers={DEMO_USER_HEADER: str(uuid.uuid4())}).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"contact_name": "   "},
        {"contact_email": "not-an-email"},
        {"category": "tax"},
        {"description": ""},
    ],
)
def test_invalid_inputs_are_rejected(
    client: TestClient, db_session: Session, overrides: dict[str, str]
) -> None:
    response = client.post(
        "/api/leads", json=lead_payload(**overrides), headers=as_user(db_session, "alice@example.com")
    )
    assert response.status_code == 422


# --- meta and mock sign-in ------------------------------------------------------------


def test_demo_users_and_me(client: TestClient, db_session: Session) -> None:
    users = client.get("/api/auth/demo-users").json()
    sarah = next(u for u in users if u["email"] == "sarah@firm-a.example.com")
    assert sarah["role"] == "ATTORNEY"
    assert sarah["firm"]["name"].startswith("Alder")

    me = client.get("/api/auth/me", headers={DEMO_USER_HEADER: sarah["id"]}).json()
    assert me["id"] == sarah["id"]
