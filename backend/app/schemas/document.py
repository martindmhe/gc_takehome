import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class UploaderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    role: UserRole


class DocumentRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: UploaderSummary
    created_at: datetime


class DocumentListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)
