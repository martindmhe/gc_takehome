"""Query parameters for the admin search endpoints (GET /api/admin/...)."""

import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, StringConstraints, field_validator

from app.models.enums import CaseStatus, Category, LeadStatus
from app.models.normalize import normalize_region
from app.schemas.common import PageParams

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
