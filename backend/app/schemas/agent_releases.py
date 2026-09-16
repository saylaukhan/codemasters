"""Requests and responses of the agent release admin API (ТЗ п. 20; plan.md §4.6, §10; T-50).

A release is an MSI build the agent downloads and verifies by SHA-256 before installing
(plan.md §4.6); agents get it from ``GET /api/agent/releases/latest`` and ``latest_version``
of their configuration. Version, link and hash are fixed once published: a fix is a new release.
A release is withdrawn with ``is_active``, never deleted.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page

# Release channel: pilot agents get a release first, the rest after promotion to stable.
type AgentChannel = Literal["pilot", "stable"]

SHA256_PATTERN = "^[0-9a-f]{64}$"


class AgentReleaseCreate(BaseModel):
    """New agent release; ``released_at`` is set by the server."""

    version: str = Field(
        max_length=32,
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
        examples=["0.2.0"],
        description="Версия MSI: major.minor.patch",
    )
    channel: AgentChannel
    download_url: str = Field(
        min_length=1,
        max_length=2048,
        examples=["https://monitor.example.kz/downloads/VKO-Agent-0.2.0.msi"],
    )
    sha256: str = Field(
        pattern=SHA256_PATTERN, description="SHA-256 файла MSI, hex в нижнем регистре"
    )
    notes: str | None = Field(default=None, max_length=2000, description="Что изменилось")


class AgentReleaseUpdate(BaseModel):
    """Promotion to another channel or withdrawal of a release."""

    channel: AgentChannel | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("channel", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class AgentReleaseDetail(BaseModel):
    """Published agent release."""

    id: int
    version: str = Field(examples=["0.2.0"])
    channel: AgentChannel
    download_url: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    notes: str | None = Field(description="Что изменилось")
    is_active: bool = Field(description="false — релиз отозван и агентам не выдаётся")
    released_at: datetime


class AgentReleaseDetailPage(Page[AgentReleaseDetail]):
    """Page of the agent releases, newest first."""
