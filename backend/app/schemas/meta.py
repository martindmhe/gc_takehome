from pydantic import BaseModel

from app.schemas.common import Option


class MetaResponse(BaseModel):
    categories: list[Option]
    # Regions with routing rules. Leads may use other regions; those stay pending.
    regions: list[Option]
