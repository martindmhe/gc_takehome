"""Idempotent demo seed data: `python -m app.seed`.

Every row has a fixed, deterministic id and is inserted with
`ON CONFLICT DO NOTHING`, so running the seed again changes nothing. All people,
firms and emails are fictional (`example.com` is reserved for documentation).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Firm, RoutingRule, User
from app.models.enums import Category, UserRole
from app.models.normalize import normalize_region

_NAMESPACE = uuid.UUID("6f1c2a52-3d4e-4b8a-9c71-0d5e2f8a1b3c")


def _seed_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, key)


@dataclass(frozen=True)
class DemoFirm:
    key: str
    name: str


@dataclass(frozen=True)
class DemoUser:
    display_name: str
    email: str
    role: UserRole
    firm_key: str | None = None


FIRMS = [
    DemoFirm("firm_a", "Alder & Associates (Firm A)"),
    DemoFirm("firm_b", "Birchwood Legal (Firm B)"),
    DemoFirm("firm_c", "Cedar Point Law (Firm C)"),
]

USERS = [
    DemoUser("Alice Plaintiff", "alice@example.com", UserRole.PLAINTIFF),
    DemoUser("Bob Plaintiff", "bob@example.com", UserRole.PLAINTIFF),
    DemoUser("Sarah Attorney", "sarah@firm-a.example.com", UserRole.ATTORNEY, "firm_a"),
    DemoUser("James Paralegal", "james@firm-a.example.com", UserRole.PARALEGAL, "firm_a"),
    DemoUser("Emily Attorney", "emily@firm-b.example.com", UserRole.ATTORNEY, "firm_b"),
    DemoUser("David Paralegal", "david@firm-b.example.com", UserRole.PARALEGAL, "firm_b"),
    DemoUser("Carmen Attorney", "carmen@firm-c.example.com", UserRole.ATTORNEY, "firm_c"),
    DemoUser("Platform Admin", "admin@example.com", UserRole.ADMIN),
]

# (region, category) -> firm. Pairs not listed here have no rule, so leads for
# them stay PENDING_ASSIGNMENT for an admin (e.g. florida / immigration).
ROUTING_RULES: dict[tuple[str, Category], str] = {
    ("california", Category.PERSONAL_INJURY): "firm_a",
    ("california", Category.EMPLOYMENT): "firm_a",
    ("new york", Category.PERSONAL_INJURY): "firm_a",
    ("new york", Category.FAMILY): "firm_b",
    ("texas", Category.EMPLOYMENT): "firm_b",
    ("texas", Category.IMMIGRATION): "firm_b",
    ("florida", Category.PERSONAL_INJURY): "firm_c",
}


def seed(db: Session) -> None:
    """Insert any missing demo rows in one transaction."""
    with db.begin():
        db.execute(
            insert(Firm)
            .values([{"id": _seed_id(f"firm:{f.key}"), "name": f.name} for f in FIRMS])
            .on_conflict_do_nothing()
        )
        db.execute(
            insert(User)
            .values(
                [
                    {
                        "id": _seed_id(f"user:{u.email}"),
                        "display_name": u.display_name,
                        "email": u.email,
                        "role": u.role,
                        "firm_id": _seed_id(f"firm:{u.firm_key}") if u.firm_key else None,
                    }
                    for u in USERS
                ]
            )
            .on_conflict_do_nothing()
        )
        db.execute(
            insert(RoutingRule)
            .values(
                [
                    {
                        "id": _seed_id(f"routing:{region}:{category}"),
                        "region": normalize_region(region),
                        "category": category,
                        "firm_id": _seed_id(f"firm:{firm_key}"),
                    }
                    for (region, category), firm_key in ROUTING_RULES.items()
                ]
            )
            .on_conflict_do_nothing()
        )


def main() -> None:
    from app.db.init_db import init_db
    from app.db.session import SessionLocal, engine

    init_db(engine)
    with SessionLocal() as db:
        seed(db)

    print(f"Seeded {len(FIRMS)} firms, {len(USERS)} users, {len(ROUTING_RULES)} routing rules.")
    print("Demo accounts (mock sign-in, no passwords):")
    for u in USERS:
        print(f"  {u.role.value:<10} {u.email}")


if __name__ == "__main__":
    main()
