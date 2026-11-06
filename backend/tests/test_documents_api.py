"""PDF upload, listing, and authorized download (against the seeded demo data).

Seed: California + employment routes to Firm A (Sarah). Emily is Firm B.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.current_user import DEMO_USER_HEADER
from app.config import get_settings
from app.db.session import engine
from app.main import app
from app.models import AuditEvent, Document, Firm, Lead, User
from app.seed import seed
from app.storage.files import LocalFileStorage, get_storage
from tests.factories import make_firm, make_lead, make_user
from tests.helpers import as_user, submit_lead

ALICE = "alice@example.com"
BOB = "bob@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"


def make_pdf(text: str = "Hello") -> bytes:
    """A small but complete one-page PDF."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


PDF = make_pdf()


@pytest.fixture(autouse=True)
def _seeded(db_session: Session) -> None:
    seed(db_session)


@pytest.fixture
def storage_dir(tmp_path: Path) -> Iterator[Path]:
    """Store uploads in a temporary directory instead of backend/var/uploads."""
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path)
    yield tmp_path
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture
def lead(client: TestClient, db_session: Session, storage_dir: Path) -> dict[str, Any]:
    """Alice's lead, assigned to Firm A and not yet accepted."""
    return submit_lead(client, as_user(db_session, ALICE))


def _upload(
    client: TestClient,
    headers: dict[str, str],
    lead_id: str,
    content: bytes = PDF,
    filename: str = "intake.pdf",
    content_type: str = "application/pdf",
) -> Any:
    return client.post(
        f"/api/leads/{lead_id}/documents",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def _stored_files(storage_dir: Path) -> list[Path]:
    return [p for p in storage_dir.rglob("*") if p.is_file()]


def test_plaintiff_uploads_a_pdf_and_gets_the_same_bytes_back(
    client: TestClient, db_session: Session, lead: dict[str, Any], storage_dir: Path
) -> None:
    alice = as_user(db_session, ALICE)

    response = _upload(client, alice, lead["id"], filename="../../My intake.pdf")
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["original_filename"] == "My intake.pdf"  # path parts dropped
    assert doc["size_bytes"] == len(PDF)
    assert doc["uploaded_by"]["display_name"] == "Alice Plaintiff"
    assert "storage_key" not in doc

    page = client.get(f"/api/leads/{lead['id']}/documents", headers=alice).json()
    assert [d["id"] for d in page["items"]] == [doc["id"]]

    download = client.get(f"/api/documents/{doc['id']}/download", headers=alice)
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["content-disposition"].startswith("inline;")

    # Stored under a generated key inside the storage directory, not the client's name.
    [stored] = _stored_files(storage_dir)
    assert stored.read_bytes() == PDF
    assert "intake" not in stored.name


def test_assigned_firm_can_view_and_upload(
    client: TestClient, db_session: Session, lead: dict[str, Any]
) -> None:
    sarah = as_user(db_session, SARAH)
    doc = _upload(client, as_user(db_session, ALICE), lead["id"]).json()

    assert client.get(f"/api/documents/{doc['id']}/download", headers=sarah).content == PDF
    assert _upload(client, sarah, lead["id"], filename="retainer.pdf").status_code == 201
    assert client.get(f"/api/leads/{lead['id']}/documents", headers=sarah).json()["total"] == 2


def test_other_plaintiffs_and_firms_cannot_access(
    client: TestClient, db_session: Session, lead: dict[str, Any]
) -> None:
    doc = _upload(client, as_user(db_session, ALICE), lead["id"]).json()

    for email in (BOB, EMILY):
        headers = as_user(db_session, email)
        assert client.get(f"/api/documents/{doc['id']}/download", headers=headers).status_code == 404
        assert client.get(f"/api/leads/{lead['id']}/documents", headers=headers).status_code == 404
        assert _upload(client, headers, lead["id"]).status_code == 404


def test_unauthorized_download_is_blocked(
    client: TestClient, db_session: Session, lead: dict[str, Any]
) -> None:
    doc = _upload(client, as_user(db_session, ALICE), lead["id"]).json()
    url = f"/api/documents/{doc['id']}/download"

    assert client.get(url).status_code == 401  # not signed in
    assert client.get(url, headers={DEMO_USER_HEADER: str(uuid.uuid4())}).status_code == 401

    # Once Firm A declines, it loses access to the lead's documents.
    sarah = as_user(db_session, SARAH)
    assert client.get(url, headers=sarah).status_code == 200
    assert client.post(f"/api/leads/{lead['id']}/decline", headers=sarah).status_code == 200
    assert client.get(url, headers=sarah).status_code == 404


def test_admin_can_download_but_not_upload(
    client: TestClient, db_session: Session, lead: dict[str, Any]
) -> None:
    admin = as_user(db_session, ADMIN)
    doc = _upload(client, as_user(db_session, ALICE), lead["id"]).json()

    assert client.get(f"/api/documents/{doc['id']}/download", headers=admin).content == PDF
    assert _upload(client, admin, lead["id"]).status_code == 403


@pytest.mark.parametrize(
    ("content", "content_type", "expected"),
    [
        (b"just some text", "application/pdf", 415),  # wrong signature
        (PDF, "text/plain", 415),  # wrong content type
        (b"", "application/pdf", 415),  # empty
        (PDF + b"0" * 2000, "application/pdf", 413),  # over the (lowered) limit
    ],
)
def test_invalid_files_are_rejected_and_nothing_is_stored(
    client: TestClient,
    db_session: Session,
    lead: dict[str, Any],
    storage_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    content_type: str,
    expected: int,
) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_bytes", len(PDF) + 1000)

    response = _upload(client, as_user(db_session, ALICE), lead["id"], content, content_type=content_type)

    assert response.status_code == expected, response.text
    assert _stored_files(storage_dir) == []
    with db_session.begin():
        assert db_session.scalars(select(Document)).all() == []


def test_stored_file_is_removed_if_saving_metadata_fails(
    client: TestClient,
    db_session: Session,
    lead: dict[str, Any],
    storage_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise RuntimeError("database write failed")

    monkeypatch.setattr("app.services.documents.record_event", fail)

    with pytest.raises(RuntimeError):
        _upload(client, as_user(db_session, ALICE), lead["id"])
    assert _stored_files(storage_dir) == []


def test_pre_acceptance_documents_appear_on_the_case(
    client: TestClient, db_session: Session, lead: dict[str, Any]
) -> None:
    doc = _upload(client, as_user(db_session, ALICE), lead["id"]).json()

    sarah = as_user(db_session, SARAH)
    case = client.post(f"/api/leads/{lead['id']}/accept", headers=sarah).json()

    # Case pages reach documents through the case's lead.
    page = client.get(f"/api/leads/{case['lead']['id']}/documents", headers=sarah).json()
    assert [d["id"] for d in page["items"]] == [doc["id"]]


# --- persistence -------------------------------------------------------------------------


@pytest.fixture
def committed_lead() -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    """A really-committed lead and its plaintiff, cleaned up afterwards."""
    with Session(engine, expire_on_commit=False) as db, db.begin():
        firm = make_firm(db, f"Persistence Firm {uuid.uuid4().hex[:6]}")
        plaintiff = make_user(db)
        lead = make_lead(db, plaintiff, firm)
        ids = (lead.id, plaintiff.id, firm.id)

    try:
        yield ids[0], ids[1]
    finally:
        lead_id, plaintiff_id, firm_pk = ids
        with Session(engine) as db, db.begin():
            doc_ids = select(Document.id).where(Document.lead_id == lead_id)
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_(doc_ids)))
            db.execute(delete(Document).where(Document.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(User).where(User.id == plaintiff_id))
            db.execute(delete(Firm).where(Firm.id == firm_pk))


def test_document_metadata_persists_in_postgres(
    committed_lead: tuple[uuid.UUID, uuid.UUID], tmp_path: Path
) -> None:
    lead_id, plaintiff_id = committed_lead
    headers = {DEMO_USER_HEADER: str(plaintiff_id)}
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path)
    try:
        # A real app with real (committing) sessions.
        with TestClient(app) as client:
            response = _upload(client, headers, str(lead_id), filename="médical report.pdf")
            assert response.status_code == 201, response.text
    finally:
        app.dependency_overrides.clear()

    with Session(engine) as db:
        document = db.scalars(select(Document).where(Document.lead_id == lead_id)).one()
        assert document.original_filename == "médical report.pdf"
        assert document.content_type == "application/pdf"
        assert document.size_bytes == len(PDF)
        assert document.uploaded_by_user_id == plaintiff_id
        assert (tmp_path / document.storage_key).read_bytes() == PDF
        event = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == document.id)).one()
        assert event.action == "document.uploaded"
