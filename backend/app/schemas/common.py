from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Option(BaseModel):
    """A stored value and its display label."""

    value: str
    label: str


MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    """`page` (1-based) and `page_size` query parameters."""

    # Capped so the offset always fits in a PostgreSQL bigint.
    page: int = Field(1, ge=1, le=1_000_000)
    page_size: int = Field(25, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class NumberedPage(BaseModel, Generic[T]):

    items: list[T]
    total: int
    page: int
    page_size: int
