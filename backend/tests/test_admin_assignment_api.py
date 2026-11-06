"""Admin assignment/reassignment and audit history.

Seed: California + employment routes to Firm A (Sarah, James). Emily is Firm B.
"""

import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.main import app
from app.models import AuditEvent, CaseNote, Firm, Lead, LegalCase, User
from app.models.enums import Category, LeadStatus, UserRole
from app.seed import seed
from app.services import admin as admin_service
from app.services import leads as lead_service
from app.services.errors import ConflictError, NotFoundError
from app.storage.files import LocalFileStorage, get_storage
from tests.helpers import as_user, firm_id, submit_lead, user_by_email
from tests.test_documents_api import make_pdf

ALICE = "alice@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
JAMES = "james@firm-a.example.com"  # Firm A paralegal
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"

FIRM_A = "Alder & Associates (Firm A)"
FIRM_B = "Birchwood Legal (Firm B)"


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


@pytest.fixture(autouse=True)
def storage_dir(tmp_path: Path) -> Iterator[Path]:
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path)
    yield tmp_path
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture
def h(db_session: Session) -> dict[str, dict[str, str]]:
    """Request headers per demo user."""
    return {name: as_user(db_session, email) for name, email in [
        ("alice", ALICE), ("sarah", SARAH), ("james", JAMES), ("emily", EMILY), ("admin", ADMIN)
    ]}


def _accepted_case(client: TestClient, h: dict[str, dict[str, str]]) -> dict[str, Any]:
    lead = submit_lead(client, h["alice"])
    response = client.post(f"/api/leads/{lead['id']}/accept", headers=h["sarah"])
    assert response.status_code == 201, response.text
    return response.json()


def _assign(client: TestClient, headers: dict[str, str], lead_id: str, firm: str) -> Any:
    return client.post(f"/api/admin/leads/{lead_id}/assign", json={"firm_id": firm}, headers=headers)


def _reassign(client: TestClient, headers: dict[str, str], case_id: str, firm: str) -> Any:
    return client.post(f"/api/admin/cases/{case_id}/reassign", json={"firm_id": firm}, headers=headers)


def _history(client: TestClient, headers: dict[str, str], kind: str, record_id: str, **params: Any) -> Any:
    response = client.get(f"/api/admin/{kind}/{record_id}/history", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_case_reassignment_end_to_end(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    firm_a, firm_b = firm_id(db_session, "Alder"), firm_id(db_session, "Birchwood")

    # 1. Alice submits a lead routed to Firm A.
    lead = submit_lead(client, h["alice"])
    assert lead["status"] == "ASSIGNED" and lead["assigned_firm"]["id"] == firm_a

    # 2. Firm A accepts, creating a case.
    response = client.post(f"/api/leads/{lead['id']}/accept", headers=h["sarah"])
    assert response.status_code == 201
    case = response.json()
    case_url, notes_url = f"/api/cases/{case['id']}", f"/api/cases/{case['id']}/notes"

    # 3. Firm A uploads a PDF and adds a private note.
    pdf = make_pdf("Pay stubs")
    response = client.post(
        f"/api/leads/{lead['id']}/documents",
        files={"file": ("paystubs.pdf", pdf, "application/pdf")},
        headers=h["sarah"],
    )
    assert response.status_code == 201
    download_url = f"/api/documents/{response.json()['id']}/download"
    response = client.post(notes_url, json={"content": "Firm A strategy"}, headers=h["sarah"])
    assert response.status_code == 201
    note_id = response.json()["id"]

    # 4. Admin reassigns the case to Firm B.
    response = _reassign(client, h["admin"], case["id"], firm_b)
    assert response.status_code == 200, response.text
    assert response.json()["assigned_firm"]["name"] == FIRM_B

    # 5-7. Firm A loses the case, the lead, the PDF, and its own notes on it.
    for staff in (h["sarah"], h["james"]):
        assert client.get(case_url, headers=staff).status_code == 404
        assert client.get(f"/api/leads/{lead['id']}", headers=staff).status_code == 404
        assert client.get(download_url, headers=staff).status_code == 404
        assert client.get(f"/api/leads/{lead['id']}/documents", headers=staff).status_code == 404
        assert client.get(notes_url, headers=staff).status_code == 404
        assert client.post(notes_url, json={"content": "x"}, headers=staff).status_code == 404
        assert client.get("/api/cases", headers=staff).json()["total"] == 0

    # 8. Firm B can read the case, its lead, and the PDF.
    assert client.get(case_url, headers=h["emily"]).json()["assigned_firm"]["id"] == firm_b
    assert client.get(f"/api/leads/{lead['id']}", headers=h["emily"]).status_code == 200
    assert client.get(download_url, headers=h["emily"]).content == pdf

    # 9. Firm B can't read Firm A's private note.
    assert client.get(notes_url, headers=h["emily"]).json() == {
        "items": [], "total": 0, "limit": 20, "offset": 0
    }

    # 10. Alice still sees her case and PDF.
    assert client.get(case_url, headers=h["alice"]).status_code == 200
    assert client.get(download_url, headers=h["alice"]).content == pdf

    # 11. Admin can inspect Firm A's note, still owned by Firm A.
    notes = client.get(notes_url, headers=h["admin"]).json()["items"]
    assert [(n["id"], n["owner_firm"]["id"]) for n in notes] == [(note_id, firm_a)]
    with db_session.begin():
        assert db_session.get(CaseNote, uuid.UUID(note_id)).owner_firm_id == uuid.UUID(firm_a)  # type: ignore[union-attr]

    # Lead and case agree on the new firm in the database.
    with db_session.begin():
        db_lead = db_session.get(Lead, uuid.UUID(lead["id"]))
        db_case = db_session.get(LegalCase, uuid.UUID(case["id"]))
        assert db_lead and db_case
        assert db_lead.assigned_firm_id == db_case.assigned_firm_id == uuid.UUID(firm_b)
        assert db_lead.status == LeadStatus.ACCEPTED

    # 12. History names the admin and shows the change, oldest first.
    admin_name = user_by_email(db_session, ADMIN).display_name
    history = _history(client, h["admin"], "cases", case["id"])
    assert [e["action"] for e in history["items"]] == [
        "lead.submitted",
        "lead.routed",
        "lead.accepted",
        "case.created",
        "document.uploaded",
        "note.created",
        "case.reassigned",
        "lead.reassigned",
    ]
    routed = history["items"][1]
    assert routed["actor"] is None  # SYSTEM
    assert routed["description"] == f"Automatically routed to {FIRM_A}"
    reassigned = history["items"][6]
    assert reassigned["actor"]["display_name"] == admin_name
    assert reassigned["actor"]["role"] == "ADMIN"
    assert reassigned["old_values"] == {"assigned_firm_id": firm_a}
    assert reassigned["new_values"] == {"assigned_firm_id": firm_b}
    assert reassigned["description"] == f"Case reassigned from {FIRM_A} to {FIRM_B}"
    # Note content never goes into the audit trail.
    assert "Firm A strategy" not in str(history)

    # The lead's own history shows the move too.
    lead_actions = [e["action"] for e in _history(client, h["admin"], "leads", lead["id"])["items"]]
    assert lead_actions[-1] == "lead.reassigned"
    assert "case.created" not in lead_actions


def test_admin_assigns_an_unmatched_lead(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    firm_b = firm_id(db_session, "Birchwood")
    lead = submit_lead(client, h["alice"], region="Nowhere")  # no routing rule
    assert lead["status"] == "PENDING_ASSIGNMENT"
    assert client.get(f"/api/leads/{lead['id']}", headers=h["emily"]).status_code == 404

    response = _assign(client, h["admin"], lead["id"], firm_b)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ASSIGNED"
    assert response.json()["assigned_firm"]["name"] == FIRM_B

    # Firm B can now see it in its inbox and accept it.
    inbox = client.get("/api/leads", headers=h["emily"]).json()
    assert [item["id"] for item in inbox["items"]] == [lead["id"]]
    assert client.post(f"/api/leads/{lead['id']}/accept", headers=h["emily"]).status_code == 201

    event = _history(client, h["admin"], "leads", lead["id"])["items"][2]
    assert event["action"] == "lead.assigned"
    assert event["old_values"] == {"status": "PENDING_ASSIGNMENT", "assigned_firm_id": None}
    assert event["new_values"] == {"status": "ASSIGNED", "assigned_firm_id": firm_b}
    assert event["description"] == f"Lead assigned to {FIRM_B} (was pending assignment)"


def test_admin_reassigns_a_declined_lead(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    firm_b = firm_id(db_session, "Birchwood")
    lead = submit_lead(client, h["alice"])
    assert client.post(f"/api/leads/{lead['id']}/decline", headers=h["sarah"]).status_code == 200

    response = _assign(client, h["admin"], lead["id"], firm_b)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ASSIGNED"
    assert client.get(f"/api/leads/{lead['id']}", headers=h["emily"]).status_code == 200
    assert client.get(f"/api/leads/{lead['id']}", headers=h["sarah"]).status_code == 404

    actions = [
        (e["action"], e["description"])
        for e in _history(client, h["admin"], "leads", lead["id"])["items"]
    ]
    assert actions[-2:] == [
        ("lead.declined", f"Declined by {FIRM_A}; lead is unassigned"),
        ("lead.assigned", f"Lead assigned to {FIRM_B} (was declined)"),
    ]


def test_admin_moves_an_assigned_lead_to_another_firm(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    lead = submit_lead(client, h["alice"])
    firm_b = firm_id(db_session, "Birchwood")

    assert _assign(client, h["admin"], lead["id"], firm_b).status_code == 200
    # Firm A can no longer see it, so it can't accept it either.
    assert client.post(f"/api/leads/{lead['id']}/accept", headers=h["sarah"]).status_code == 404
    event = _history(client, h["admin"], "leads", lead["id"])["items"][-1]
    assert event["description"] == f"Lead reassigned from {FIRM_A} to {FIRM_B}"


def test_accepted_leads_cannot_be_reassigned_directly(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    case = _accepted_case(client, h)
    response = _assign(client, h["admin"], case["lead"]["id"], firm_id(db_session, "Birchwood"))
    assert response.status_code == 409
    assert "Reassign the case instead" in response.json()["detail"]
    # Nothing moved.
    assert client.get(f"/api/cases/{case['id']}", headers=h["sarah"]).status_code == 200


def test_case_status_and_records_survive_reassignment(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    case = _accepted_case(client, h)
    status_url = f"/api/cases/{case['id']}/status"
    assert client.patch(status_url, json={"status": "IN_PROGRESS"}, headers=h["sarah"]).status_code == 200

    moved = _reassign(client, h["admin"], case["id"], firm_id(db_session, "Birchwood")).json()
    assert moved["status"] == "IN_PROGRESS"
    assert moved["created_at"] == case["created_at"]
    assert moved["lead"] == case["lead"]

    # The new firm now manages progress; the old one can't.
    assert client.patch(status_url, json={"status": "CLOSED"}, headers=h["emily"]).status_code == 200
    assert client.patch(status_url, json={"status": "OPEN"}, headers=h["sarah"]).status_code == 404


def test_reassignment_requires_a_different_existing_firm(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    case = _accepted_case(client, h)
    firm_a = firm_id(db_session, "Alder")

    response = _reassign(client, h["admin"], case["id"], firm_a)
    assert response.status_code == 409
    assert response.json()["detail"] == f"This case is already assigned to {FIRM_A}"

    assert _reassign(client, h["admin"], case["id"], str(uuid.uuid4())).status_code == 422
    assert _reassign(client, h["admin"], str(uuid.uuid4()), firm_a).status_code == 404
    response = client.post(
        f"/api/admin/cases/{case['id']}/reassign",
        json={"firm_id": firm_a, "status": "CLOSED"},  # only firm_id is accepted
        headers=h["admin"],
    )
    assert response.status_code == 422

    lead = submit_lead(client, h["alice"])
    assert _assign(client, h["admin"], lead["id"], firm_a).status_code == 409  # already there
    assert _assign(client, h["admin"], lead["id"], str(uuid.uuid4())).status_code == 422

    # Failed attempts leave no trace in the history.
    actions = [e["action"] for e in _history(client, h["admin"], "cases", case["id"])["items"]]
    assert "case.reassigned" not in actions


def test_only_admins_can_reassign_or_read_history(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    case = _accepted_case(client, h)
    lead = submit_lead(client, h["alice"], region="Nowhere")
    firm_b = firm_id(db_session, "Birchwood")

    for who in ("alice", "sarah", "james", "emily"):
        headers = h[who]
        assert _reassign(client, headers, case["id"], firm_b).status_code == 403
        assert _assign(client, headers, lead["id"], firm_b).status_code == 403
        assert client.get(f"/api/admin/cases/{case['id']}/history", headers=headers).status_code == 403
        assert client.get(f"/api/admin/leads/{lead['id']}/history", headers=headers).status_code == 403
    assert _reassign(client, {}, case["id"], firm_b).status_code == 401

    # Nothing changed.
    assert client.get(f"/api/cases/{case['id']}", headers=h["sarah"]).status_code == 200
    assert client.get(f"/api/leads/{lead['id']}", headers=h["alice"]).json()["status"] == "PENDING_ASSIGNMENT"


def test_history_is_paginated_oldest_first(
    client: TestClient, db_session: Session, h: dict[str, dict[str, str]]
) -> None:
    case = _accepted_case(client, h)
    firms = [firm_id(db_session, p) for p in ("Birchwood", "Alder", "Birchwood")]
    for firm in firms:
        assert _reassign(client, h["admin"], case["id"], firm).status_code == 200

    full = _history(client, h["admin"], "cases", case["id"])
    assert full["total"] == 4 + 2 * len(firms)
    pages = [_history(client, h["admin"], "cases", case["id"], page=n, page_size=3)["items"] for n in (1, 2, 3, 4)]
    assert [e["id"] for page in pages for e in page] == [e["id"] for e in full["items"]]
    times = [e["created_at"] for e in full["items"]]
    assert times == sorted(times)

    with db_session.begin():
        assert db_session.get(LegalCase, uuid.UUID(case["id"])).assigned_firm_id == uuid.UUID(firms[-1])  # type: ignore[union-attr]
    assert client.get(f"/api/admin/cases/{case['id']}/history", params={"page_size": 101},
                      headers=h["admin"]).status_code == 422
    assert client.get(f"/api/admin/cases/{uuid.uuid4()}/history", headers=h["admin"]).status_code == 404


# --- concurrency -----------------------------------------------------------------
#
# These use committed data and real concurrent sessions (the per-test rollback
# session can't be shared across threads), and clean up after themselves.


@pytest.fixture
def committed() -> Iterator[dict[str, Any]]:
    """Three firms, a staff user at the first, an admin, and a plaintiff, all committed."""
    tag = uuid.uuid4().hex[:8]
    with Session(engine, expire_on_commit=False) as db, db.begin():
        firms = [Firm(name=f"Race {tag} {n}") for n in "ABC"]
        db.add_all(firms)
        db.flush()
        staff = User(display_name="Race Staff", email=f"staff-{tag}@test.example.com",
                     role=UserRole.ATTORNEY, firm_id=firms[0].id)
        admin = User(display_name="Race Admin", email=f"admin-{tag}@test.example.com", role=UserRole.ADMIN)
        plaintiff = User(display_name="Race Plaintiff", email=f"p-{tag}@test.example.com",
                         role=UserRole.PLAINTIFF)
        db.add_all([staff, admin, plaintiff])
        db.flush()
        lead = Lead(
            plaintiff_id=plaintiff.id, contact_name="Race Plaintiff", contact_email=plaintiff.email,
            region="california", category=Category.EMPLOYMENT, description="race",
            status=LeadStatus.ASSIGNED, assigned_firm_id=firms[0].id,
        )
        db.add(lead)
        db.flush()
    data = {"firms": firms, "staff": staff, "admin": admin, "lead_id": lead.id}
    try:
        yield data
    finally:
        with Session(engine) as db, db.begin():
            case_ids = db.scalars(select(LegalCase.id).where(LegalCase.lead_id == lead.id)).all()
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_([lead.id, *case_ids])))
            db.execute(delete(LegalCase).where(LegalCase.lead_id == lead.id))
            db.execute(delete(Lead).where(Lead.id == lead.id))
            db.execute(delete(User).where(User.id.in_([staff.id, admin.id, plaintiff.id])))
            db.execute(delete(Firm).where(Firm.id.in_([f.id for f in firms])))


def _run_together(*calls: Any) -> list[object]:
    """Start every call at the same moment in its own session; return results or exceptions."""
    barrier = threading.Barrier(len(calls))
    results: list[object] = [None] * len(calls)

    def run(i: int, call: Any) -> None:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait()
            try:
                results[i] = call(db)
            except Exception as exc:  # noqa: BLE001 - asserted by the caller
                results[i] = exc

    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return results


def test_concurrent_accept_and_assign_leave_consistent_data(committed: dict[str, Any]) -> None:
    """A firm accepting while an admin moves the lead elsewhere: exactly one wins."""
    lead_id, (firm_a, firm_b, _) = committed["lead_id"], committed["firms"]
    results = _run_together(
        lambda db: lead_service.accept_lead(db, committed["staff"], lead_id),
        lambda db: admin_service.assign_lead(db, committed["admin"], lead_id, firm_b.id),
    )
    accepted, assigned = results
    # The loser gets a 409, or a 404 if the lead had already left Firm A when it looked.
    assert sum(isinstance(r, (ConflictError, NotFoundError)) for r in results) == 1, results

    with Session(engine) as db:
        lead = db.get(Lead, lead_id)
        case = db.scalar(select(LegalCase).where(LegalCase.lead_id == lead_id))
        assert lead is not None
        if isinstance(assigned, ConflictError):  # accept won; the case must be reassigned now
            assert lead.status == LeadStatus.ACCEPTED
            assert case is not None and case.assigned_firm_id == lead.assigned_firm_id == firm_a.id
        else:  # assign won; Firm A's accept found the lead was no longer theirs
            assert isinstance(accepted, (ConflictError, NotFoundError))
            assert lead.status == LeadStatus.ASSIGNED and lead.assigned_firm_id == firm_b.id
            assert case is None


def test_concurrent_case_reassignments_keep_lead_and_case_in_step(committed: dict[str, Any]) -> None:
    """Two reassignments at once run one after the other (row locks), never interleaved."""
    lead_id, (_, firm_b, firm_c) = committed["lead_id"], committed["firms"]
    with Session(engine, expire_on_commit=False) as db:
        case_id = lead_service.accept_lead(db, committed["staff"], lead_id)

    results = _run_together(
        lambda db: admin_service.reassign_case(db, committed["admin"], case_id, firm_b.id),
        lambda db: admin_service.reassign_case(db, committed["admin"], case_id, firm_c.id),
    )
    assert results == [None, None], results

    with Session(engine) as db:
        case = db.get(LegalCase, case_id)
        lead = db.get(Lead, lead_id)
        assert case and lead
        assert case.assigned_firm_id == lead.assigned_firm_id
        assert case.assigned_firm_id in (firm_b.id, firm_c.id)
        # The audit trail chains: the second move starts where the first ended.
        moves = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_id == case_id, AuditEvent.action == "case.reassigned")
            .order_by(AuditEvent.created_at)
        ).all()
        assert len(moves) == 2
        assert moves[1].old_values == moves[0].new_values
        assert moves[1].new_values == {"assigned_firm_id": str(case.assigned_firm_id)}
