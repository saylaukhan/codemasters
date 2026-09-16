"""FastAPI application factory.

Routers arrive in T-03 (with the problem+json error handler, ADR-009), the audit middleware
in T-20. For now the application exposes only ``GET /api/health``.
"""

from datetime import UTC, datetime

from fastapi import FastAPI

from app import __version__
from app.schemas.health import HealthResponse

API_PREFIX = "/api"


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application."""
    application = FastAPI(
        title="Мониторинг интернета ВКО",
        version=__version__,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )

    @application.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Liveness probe: server is up; the time is UTC (ADR-014)."""
        return HealthResponse(status="ok", version=__version__, time=datetime.now(UTC))

    return application


app = create_app()
