import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class FirmSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserSummary(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    role: UserRole


class DemoUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str
    role: UserRole
    firm: FirmSummary | None
