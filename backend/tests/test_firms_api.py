from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_firm


def test_list_firms_returns_firms_sorted_by_name(client: TestClient, db_session: Session) -> None:
    with db_session.begin():
        make_firm(db_session, "Zeta Law")
        make_firm(db_session, "Alpha Law")

    response = client.get("/api/firms")

    assert response.status_code == 200
    body = response.json()
    assert [f["name"] for f in body] == ["Alpha Law", "Zeta Law"]
    assert set(body[0]) == {"id", "name", "created_at"}
