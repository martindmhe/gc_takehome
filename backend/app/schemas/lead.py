import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field, field_validator

from app.models.enums import Category, LeadStatus
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


class LeadRead(BaseModel):
    """A lead as its viewer sees it. Omits the plaintiff's account details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_name: str
    contact_email: str
    region: str
    category: Category
    description: str
    status: LeadStatus
    assigned_firm: FirmSummary | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def region_label(self) -> str:
        return region_label(self.region)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def category_label(self) -> str:
        return self.category.label
