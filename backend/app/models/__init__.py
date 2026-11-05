"""SQLAlchemy ORM models.

Every model is imported here so `Base.metadata` is complete before `init_db`
creates tables. Add new model modules to this list.
"""

from app.db.base import Base
from app.models.audit_event import AuditEvent
from app.models.case_note import CaseNote
from app.models.document import Document
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.legal_case import LegalCase
from app.models.routing_rule import RoutingRule
from app.models.user import User

__all__ = [
    "AuditEvent",
    "Base",
    "CaseNote",
    "Document",
    "Firm",
    "Lead",
    "LegalCase",
    "RoutingRule",
    "User",
]
