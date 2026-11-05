"""Domain enumerations and reference data.

Roles and statuses are PostgreSQL enum types. Categories are stored as
canonical lowercase identifiers in a plain string column; their display labels
live here only. Regions are free-form (see `app.models.normalize`).
"""

from enum import StrEnum

from sqlalchemy import Enum


class UserRole(StrEnum):
    PLAINTIFF = "PLAINTIFF"
    ATTORNEY = "ATTORNEY"
    PARALEGAL = "PARALEGAL"
    ADMIN = "ADMIN"


# Attorneys and paralegals have identical permissions (domain contract).
FIRM_STAFF_ROLES = frozenset({UserRole.ATTORNEY, UserRole.PARALEGAL})


class LeadStatus(StrEnum):
    PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT"
    ASSIGNED = "ASSIGNED"
    DECLINED = "DECLINED"
    ACCEPTED = "ACCEPTED"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_PLAINTIFF = "WAITING_ON_PLAINTIFF"
    CLOSED = "CLOSED"


class Category(StrEnum):
    PERSONAL_INJURY = "personal_injury"
    EMPLOYMENT = "employment"
    FAMILY = "family"
    IMMIGRATION = "immigration"

    @property
    def label(self) -> str:
        return CATEGORY_LABELS[self]


CATEGORY_LABELS: dict[Category, str] = {
    Category.PERSONAL_INJURY: "Personal Injury",
    Category.EMPLOYMENT: "Employment",
    Category.FAMILY: "Family Law",
    Category.IMMIGRATION: "Immigration",
}

# Shared column types, so each PostgreSQL enum type is defined exactly once.
user_role_type = Enum(UserRole, name="user_role")
lead_status_type = Enum(LeadStatus, name="lead_status")
case_status_type = Enum(CaseStatus, name="case_status")
