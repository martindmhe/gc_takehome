import uuid
from datetime import datetime

from pydantic import AliasPath, BaseModel, ConfigDict, Field

from app.models.enums import CaseStatus
from app.schemas.lead import LeadInfo
from app.schemas.user import FirmSummary


class PlaintiffSummary(BaseModel):
    # enough plaintiff data to include on case
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str


class CaseRead(BaseModel):
    
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CaseStatus
    assigned_firm: FirmSummary
    lead: LeadInfo
    plaintiff: PlaintiffSummary = Field(validation_alias=AliasPath("lead", "plaintiff"))
    created_at: datetime
    updated_at: datetime


class CaseListParams(BaseModel):
    """Query parameters for GET /api/cases. Scope always comes from the signed-in user."""

    model_config = ConfigDict(extra="forbid")

    status: CaseStatus | None = None
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)


class CaseStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CaseStatus
