import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.user import FirmSummary, UserSummary

NOTE_MAX_LENGTH = 10_000


class NoteCreate(BaseModel):
    """Only the text comes from the client. Author and owner firm come from the
    signed-in user; extra fields such as `owner_firm_id` are rejected (422)."""

    model_config = ConfigDict(extra="forbid")

    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_MAX_LENGTH)
    ]


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    content: str
    author: UserSummary
    owner_firm: FirmSummary
    created_at: datetime


class NoteListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
