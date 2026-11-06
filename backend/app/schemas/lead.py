import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app.models.enums import CaseStatus, Category, LeadStatus
from app.models.normalize import normalize_region, region_label
from app.schemas.user import FirmSummary

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LeadCreate(BaseModel):
    # Unknown fields (e.g. plaintiff_id, status) are rejected, never silently used.
    model_config = ConfigDict(extra="forbid")

    contact_name: Annotated[Text, StringConstraints(max_length=200)]
    contact_email: Annotated[Text, StringConstraints(max_length=320)]
    region: Annotated[Text, StringConstraints(max_length=50)]
    category: Category
    description: Annotated[Text, StringConstraints(max_length=5000)]

    @field_validator("contact_email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("must be a valid email address")
        return value.lower()

    @field_validator("region")
    @classmethod
    def _normalize_region(cls, value: str) -> str:
        return normalize_region(value)


class LeadInfo(BaseModel):
    """What the plaintiff submitted. Omits the plaintiff's account details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_name: str
    contact_email: str
    region: str
    category: Category
    description: str
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def region_label(self) -> str:
        return region_label(self.region)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def category_label(self) -> str:
        return self.category.label


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CaseStatus


class LeadRead(LeadInfo):
    """A lead with its current assignment and, once accepted, its case."""

    status: LeadStatus
    assigned_firm: FirmSummary | None
    case: CaseSummary | None
    updated_at: datetime


class LeadDeclined(BaseModel):
    """Result of a decline. The decliner loses access, so only the outcome is returned."""

    id: uuid.UUID
    status: LeadStatus


class LeadSort(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"


class LeadListParams(BaseModel):
    """Query parameters for GET /api/leads.

    Unknown parameters (e.g. `firm_id`) are rejected: scope always comes from
    the signed-in user, never from the request.
    """

    model_config = ConfigDict(extra="forbid")

    status: LeadStatus | None = None
    category: Category | None = None
    region: Annotated[str, StringConstraints(max_length=50)] | None = None
    # Case-insensitive match on contact name, contact email, or description.
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    created_from: AwareDatetime | None = None  # inclusive
    created_to: AwareDatetime | None = None  # exclusive
    sort: LeadSort = LeadSort.NEWEST
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)

    @field_validator("region")
    @classmethod
    def _normalize_region(cls, value: str | None) -> str | None:
        return normalize_region(value) or None if value is not None else None

    @field_validator("q")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _date_range(self) -> Self:
        if self.created_from and self.created_to and self.created_from >= self.created_to:
            raise ValueError("created_from must be before created_to")
        return self
