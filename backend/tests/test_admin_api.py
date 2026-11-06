"""Admin search across firms: GET /api/admin/leads, /cases, /firms."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import Lead, LegalCase
from app.models.enums import CaseStatus, Category, LeadStatus
from app.seed import seed
from tests.helpers import as_user, firm_id, user_by_email

ALICE = "alice@example.com"
SARAH = "sarah@firm-a.example.com"  # Firm A attorney
JAMES = "james@firm-a.example.com"  # Firm A paralegal
EMILY = "emily@firm-b.example.com"  # Firm B attorney
ADMIN = "admin@example.com"


@dataclass
class Row:
    name: str
    email: str
    status: LeadStatus
    firm: str | None  # firm name prefix
    category: Category = Category.EMPLOYMENT
    region: str = "california"
    case_status: CaseStatus | None = None


# Oldest first. Fictional people.
ROWS = [
    Row("Riley Park", "riley@example.com", LeadStatus.ASSIGNED, "Alder"),
    Row("Jordan Vale", "jordan.vale@example.com", LeadStatus.ASSIGNED, "Birchwood", Category.FAMILY, "new york"),
    Row("Casey Moor", "casey@example.com", LeadStatus.PENDING_ASSIGNMENT, None, Category.IMMIGRATION, "texas"),
    Row("Morgan Reed", "morgan@example.com", LeadStatus.DECLINED, None),
    Row("Avery Stone", "avery@example.com", LeadStatus.ACCEPTED, "Alder", case_status=CaseStatus.OPEN),
    Row("Quinn Rivera", "quinn_r@example.com", LeadStatus.ACCEPTED, "Birchwood", Category.FAMILY,
        "new york", CaseStatus.IN_PROGRESS),
]


@pytest.fixture(autouse=True)
def data(db_session: Session) -> dict[str, uuid.UUID]:
    """Seeded users and firms plus ROWS as leads (and cases). Returns lead ids by contact name."""
    seed(db_session)
    plaintiff = user_by_email(db_session, ALICE)
    firms = {prefix: uuid.UUID(firm_id(db_session, prefix)) for prefix in ("Alder", "Birchwood")}
    start = datetime(2026, 1, 1, tzinfo=UTC)
    ids: dict[str, uuid.UUID] = {}
    with db_session.begin():
        for i, row in enumerate(ROWS):
            lead = Lead(
                plaintiff_id=plaintiff.id,
                contact_name=row.name,
                contact_email=row.email,
                region=row.region,
                category=row.category,
                description="Fictional demo lead.",
                status=row.status,
                assigned_firm_id=firms[row.firm] if row.firm else None,
                created_at=start + timedelta(hours=i),
            )
            db_session.add(lead)
            db_session.flush()
            ids[row.name] = lead.id
            if row.case_status:
                db_session.add(
                    LegalCase(
                        lead_id=lead.id,
                        assigned_firm_id=lead.assigned_firm_id,
                        status=row.case_status,
                        created_at=start + timedelta(days=1, hours=i),
                    )
                )
    return ids


def _leads(client: TestClient, db: Session, **params: Any) -> Any:
    response = client.get("/api/admin/leads", params=params, headers=as_user(db, ADMIN))
    assert response.status_code == 200, response.text
    return response.json()


def _cases(client: TestClient, db: Session, **params: Any) -> Any:
    response = client.get("/api/admin/cases", params=params, headers=as_user(db, ADMIN))
    assert response.status_code == 200, response.text
    return response.json()


def _names(page: Any) -> list[str]:
    return [item["contact_name"] for item in page["items"]]


def _case_names(page: Any) -> list[str]:
    return [item["lead"]["contact_name"] for item in page["items"]]


def test_admin_sees_leads_across_all_firms(client: TestClient, db_session: Session) -> None:
    page = _leads(client, db_session)
    assert page["total"] == len(ROWS)
    assert page["page"] == 1 and page["page_size"] == 25
    # Newest first by default.
    assert _names(page) == [row.name for row in reversed(ROWS)]

    by_name = {item["contact_name"]: item for item in page["items"]}
    assert by_name["Riley Park"]["assigned_firm"]["name"] == "Alder & Associates (Firm A)"
    assert by_name["Jordan Vale"]["assigned_firm"]["name"] == "Birchwood Legal (Firm B)"
    assert by_name["Casey Moor"]["assigned_firm"] is None  # unmatched
    assert by_name["Morgan Reed"]["assigned_firm"] is None  # declined
    assert by_name["Avery Stone"]["case"]["status"] == "OPEN"

    assert _names(_leads(client, db_session, sort="oldest"))[0] == "Riley Park"


def test_admin_sees_cases_across_all_firms(client: TestClient, db_session: Session) -> None:
    page = _cases(client, db_session)
    assert page["total"] == 2
    assert _case_names(page) == ["Quinn Rivera", "Avery Stone"]
    assert {item["assigned_firm"]["name"] for item in page["items"]} == {
        "Alder & Associates (Firm A)",
        "Birchwood Legal (Firm B)",
    }
    # Lead metadata comes along.
    assert page["items"][0]["lead"]["category_label"] == "Family Law"
    assert page["items"][0]["plaintiff"]["email"] == ALICE

    assert _case_names(_cases(client, db_session, sort="oldest")) == ["Avery Stone", "Quinn Rivera"]


def test_lead_search_and_filters(client: TestClient, db_session: Session) -> None:
    firm_b = firm_id(db_session, "Birchwood")

    # Name or email, case-insensitive substring.
    assert _names(_leads(client, db_session, q="park")) == ["Riley Park"]
    assert _names(_leads(client, db_session, q="JORDAN.VALE@")) == ["Jordan Vale"]
    assert _names(_leads(client, db_session, q="  ")) == _names(_leads(client, db_session))

    assert _names(_leads(client, db_session, status="DECLINED")) == ["Morgan Reed"]
    assert _names(_leads(client, db_session, status="PENDING_ASSIGNMENT")) == ["Casey Moor"]
    assert _names(_leads(client, db_session, category="family")) == ["Quinn Rivera", "Jordan Vale"]
    assert _names(_leads(client, db_session, region="New York")) == ["Quinn Rivera", "Jordan Vale"]
    assert _names(_leads(client, db_session, firm_id=firm_b)) == ["Quinn Rivera", "Jordan Vale"]

    # Filters combine.
    assert _names(_leads(client, db_session, firm_id=firm_b, status="ACCEPTED", q="quinn")) == [
        "Quinn Rivera"
    ]
    assert _leads(client, db_session, firm_id=firm_b, q="riley")["total"] == 0


def test_case_search_and_filters(client: TestClient, db_session: Session) -> None:
    firm_a = firm_id(db_session, "Alder")

    assert _case_names(_cases(client, db_session, q="avery@")) == ["Avery Stone"]
    assert _case_names(_cases(client, db_session, q="rivera")) == ["Quinn Rivera"]
    # Leads without a case never show up in case search.
    assert _cases(client, db_session, q="riley")["total"] == 0
    assert _case_names(_cases(client, db_session, status="IN_PROGRESS")) == ["Quinn Rivera"]
    assert _case_names(_cases(client, db_session, firm_id=firm_a)) == ["Avery Stone"]
    assert _cases(client, db_session, firm_id=firm_a, status="IN_PROGRESS")["total"] == 0


def test_invalid_params_are_rejected(client: TestClient, db_session: Session) -> None:
    admin = as_user(db_session, ADMIN)
    for url, params in [
        ("/api/admin/leads", {"page_size": 101}),
        ("/api/admin/leads", {"page_size": 0}),
        ("/api/admin/leads", {"page": 0}),
        ("/api/admin/leads", {"status": "NOPE"}),
        ("/api/admin/leads", {"firm_id": "not-a-uuid"}),
        ("/api/admin/leads", {"surprise": "1"}),
        ("/api/admin/cases", {"page_size": 101}),
        ("/api/admin/cases", {"category": "family"}),  # not a case filter
        ("/api/admin/firms", {"page_size": 101}),
    ]:
        assert client.get(url, params=params, headers=admin).status_code == 422, (url, params)


@pytest.fixture
def statements() -> Iterator[list[tuple[str, Any]]]:
    """Every SQL statement (and its parameters) sent to the database during the test."""
    captured: list[tuple[str, Any]] = []

    def capture(_conn: Any, _cursor: Any, sql: str, parameters: Any, *_: Any) -> None:
        captured.append((sql, parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield captured
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_pagination_is_applied_in_sql(
    client: TestClient, db_session: Session, statements: list[tuple[str, Any]]
) -> None:
    newest_first = [row.name for row in reversed(ROWS)]
    pages = [_leads(client, db_session, page=n, page_size=4) for n in (1, 2, 3)]

    assert [_names(p) for p in pages] == [newest_first[:4], newest_first[4:], []]
    assert all(p["total"] == len(ROWS) and p["page_size"] == 4 for p in pages)
    assert [p["page"] for p in pages] == [1, 2, 3]

    # The database did the paging: each page's query sent LIMIT 4 OFFSET (page-1)*4,
    # and the total came from a COUNT(*) query rather than fetching every row.
    lead_queries = [(sql, params) for sql, params in statements if "FROM leads" in sql]
    paged = [params for sql, params in lead_queries if "LIMIT %(param_1)s" in sql]
    assert [(p["param_1"], p["param_2"]) for p in paged] == [(4, 0), (4, 4), (4, 8)]
    assert sum("count(*)" in sql for sql, _ in lead_queries) == 3

    case_page = _cases(client, db_session, page=2, page_size=1)
    assert case_page["total"] == 2 and _case_names(case_page) == ["Avery Stone"]


def test_firms_are_listed_for_admins(client: TestClient, db_session: Session) -> None:
    response = client.get("/api/admin/firms", headers=as_user(db_session, ADMIN))
    assert response.status_code == 200
    page = response.json()
    names = [f["name"] for f in page["items"]]
    assert names == sorted(names)
    assert "Alder & Associates (Firm A)" in names and page["total"] == len(names)


@pytest.mark.parametrize("email", [ALICE, SARAH, JAMES, EMILY])
@pytest.mark.parametrize("path", ["/api/admin/leads", "/api/admin/cases", "/api/admin/firms"])
def test_non_admins_cannot_use_admin_endpoints(
    client: TestClient, db_session: Session, email: str, path: str
) -> None:
    assert client.get(path, headers=as_user(db_session, email)).status_code == 403


@pytest.mark.parametrize("path", ["/api/admin/leads", "/api/admin/cases", "/api/admin/firms"])
def test_admin_endpoints_require_sign_in(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "q",
    [
        "' OR '1'='1",
        "'; DROP TABLE leads; --",
        "riley' UNION SELECT * FROM users --",
        "%",  # a LIKE wildcard: matched literally, not as "anything"
        "\\",
    ],
)
def test_search_is_not_vulnerable_to_injection(client: TestClient, db_session: Session, q: str) -> None:
    assert _leads(client, db_session, q=q)["total"] == 0
    assert _cases(client, db_session, q=q)["total"] == 0
    with db_session.begin():
        assert db_session.scalar(select(func.count()).select_from(Lead)) == len(ROWS)


def test_wildcard_characters_match_literally(client: TestClient, db_session: Session) -> None:
    # "_" is a literal underscore: only quinn_r@ has one.
    assert _names(_leads(client, db_session, q="n_r")) == ["Quinn Rivera"]
