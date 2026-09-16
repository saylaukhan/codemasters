"""Response schema of ``GET /api/health``."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness answer of the API server."""

    status: Literal["ok"]
    version: str
    time: datetime
