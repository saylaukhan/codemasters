"""FastAPI application factory.

Errors leave the API as ``application/problem+json`` (``app/core/errors.py``, ADR-009); the
OpenAPI contract is built by ``app/core/openapi.py``. Routers of ``app/api`` are contract stubs
until their tasks land; the audit middleware arrives in T-20.
"""

from datetime import UTC, datetime

from app import __version__
from app.api import API_PREFIX, api_router
from app.core.errors import register_error_handlers
from app.core.openapi import ContractApp, operation_id
from app.schemas.health import HealthResponse


def create_app() -> ContractApp:
    """Build and return a configured FastAPI application."""
    application = ContractApp(
        title="Мониторинг интернета ВКО",
        version=__version__,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
        generate_unique_id_function=operation_id,
        separate_input_output_schemas=False,
    )
    register_error_handlers(application)

    @application.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Liveness probe: server is up; the time is UTC (ADR-014)."""
        return HealthResponse(status="ok", version=__version__, time=datetime.now(UTC))

    application.include_router(api_router)
    return application


app = create_app()
