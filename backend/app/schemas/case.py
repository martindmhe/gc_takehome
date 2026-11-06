import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CaseStatus
from app.schemas.lead import LeadInfo
from app.schemas.user import FirmSummary


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CaseStatus
    assigned_firm: FirmSummary
    lead: LeadInfo
    created_at: datetime
    updated_at: datetime
