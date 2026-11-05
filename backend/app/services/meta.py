from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoutingRule


def list_known_regions(db: Session) -> Sequence[str]:
    """Regions that appear in the routing rules. Plaintiffs may still enter others."""
    with db.begin():
        return db.scalars(
            select(RoutingRule.region).distinct().order_by(RoutingRule.region)
        ).all()
