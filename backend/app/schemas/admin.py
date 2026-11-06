"""Request and response models for the admin endpoints (/api/admin/...)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.models.enums import CaseStatus, Category, LeadStatus
from app.models.normalize import normalize_region
from app.schemas.common import PageParams
from app.schemas.user import UserSummary

SearchText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class SortOrder(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"


class _SearchParams(PageParams):
    model_config = ConfigDict(extra="forbid")

    # Case-insensitive substring of the plaintiff's contact name or email.
    q: SearchText | None = None
    # Currently assigned firm.
    firm_id: uuid.UUID | None = None
    sort: SortOrder = SortOrder.NEWEST

    @field_validator("q")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None


class AdminLeadSearchParams(_SearchParams):
    status: LeadStatus | None = None
    category: Category | None = None
    region: Annotated[str, StringConstraints(max_length=50)] | None = None

    @field_validator("region")
    @classmethod
    def _normalize_region(cls, value: str | None) -> str | None:
        return normalize_region(value) or None if value is not None else None


class AdminCaseSearchParams(_SearchParams):
    status: CaseStatus | None = None


class AdminFirmListParams(PageParams):
    model_config = ConfigDict(extra="forbid")


class FirmAssignment(BaseModel):
    """Body for assign/reassign. Only the target firm; everything else comes from the server."""

    model_config = ConfigDict(extra="forbid")

    firm_id: uuid.UUID


class HistoryParams(PageParams):
    model_config = ConfigDict(extra="forbid")


class AuditEventRead(BaseModel):
    """One history entry. `actor` is null for SYSTEM actions (e.g. automatic routing)."""

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: str
    actor: UserSummary | None
    description: str
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    created_at: datetime
