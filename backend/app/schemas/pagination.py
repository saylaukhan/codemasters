"""List envelope of every paginated endpoint: ``{items, total, page, page_size}`` (ADR-009).

A list endpoint returns a named subclass, ``class SchoolPage(Page[SchoolListItem])``: a bare
``Page[SchoolListItem]`` would appear in OpenAPI and in the panel types as ``Page_SchoolListItem_``.
"""

from pydantic import BaseModel, Field


class Page[ItemT](BaseModel):
    """One page of a list; ``total`` counts all items that match the filters."""

    items: list[ItemT]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
