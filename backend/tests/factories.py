"""Minimal row builders for database tests. Callers own the transaction."""

import uuid

from sqlalchemy.orm import Session

from app.models import Firm, Lead, LegalCase, User
from app.models.enums import Category, LeadStatus, UserRole


def make_firm(db: Session, name: str = "Test Firm") -> Firm:
    firm = Firm(name=name)
    db.add(firm)
    db.flush()
    return firm


def make_user(db: Session, role: UserRole = UserRole.PLAINTIFF, firm: Firm | None = None) -> User:
    user = User(
        display_name=f"Test {role.value.title()}",
        email=f"{uuid.uuid4().hex}@test.example.com",
        role=role,
        firm_id=firm.id if firm else None,
    )
    db.add(user)
    db.flush()
    return user


def make_lead(db: Session, plaintiff: User, firm: Firm | None = None, status: LeadStatus | None = None) -> Lead:
    lead = Lead(
        plaintiff_id=plaintiff.id,
        contact_name=plaintiff.display_name,
        contact_email=plaintiff.email,
        region="california",
        category=Category.EMPLOYMENT,
        description="Test lead",
        status=status or (LeadStatus.ASSIGNED if firm else LeadStatus.PENDING_ASSIGNMENT),
        assigned_firm_id=firm.id if firm else None,
    )
    db.add(lead)
    db.flush()
    return lead


def make_case(db: Session, lead: Lead, firm: Firm) -> LegalCase:
    case = LegalCase(lead_id=lead.id, assigned_firm_id=firm.id)
    db.add(case)
    db.flush()
    return case
