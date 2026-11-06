import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import RoutingRule
from app.models.enums import Category, LeadStatus, UserRole
from tests.factories import make_case, make_firm, make_lead, make_user


def test_routing_rule_region_category_is_unique(db_session: Session) -> None:
    with db_session.begin():
        firm_a, firm_b = make_firm(db_session, "A"), make_firm(db_session, "B")
        db_session.add(RoutingRule(region="texas", category=Category.FAMILY, firm_id=firm_a.id))

    with pytest.raises(IntegrityError, match="uq_routing_rules_region_category"):
        with db_session.begin():
            db_session.add(RoutingRule(region="texas", category=Category.FAMILY, firm_id=firm_b.id))


def test_lead_cannot_have_two_cases(db_session: Session) -> None:
    with db_session.begin():
        firm = make_firm(db_session)
        lead = make_lead(db_session, make_user(db_session), firm, LeadStatus.ACCEPTED)
        make_case(db_session, lead, firm)

    with pytest.raises(IntegrityError, match="cases_lead_id_key"):
        with db_session.begin():
            make_case(db_session, lead, firm)


@pytest.mark.parametrize("role", [UserRole.ATTORNEY, UserRole.PARALEGAL])
def test_firm_staff_require_a_firm(db_session: Session, role: UserRole) -> None:
    with pytest.raises(IntegrityError, match="ck_users_firm_staff_has_firm"):
        with db_session.begin():
            make_user(db_session, role)


@pytest.mark.parametrize(
    ("status", "with_firm"),
    [
        (LeadStatus.ASSIGNED, False),
        (LeadStatus.DECLINED, True),
    ],
)
def test_lead_firm_must_match_status(db_session: Session, status: LeadStatus, with_firm: bool) -> None:
    with pytest.raises(IntegrityError, match="ck_leads_firm_matches_status"):
        with db_session.begin():
            plaintiff = make_user(db_session)
            make_lead(db_session, plaintiff, make_firm(db_session) if with_firm else None, status)
