"""FastAPI application factory.

Errors leave the API as ``application/problem+json`` (``app/core/errors.py``, ADR-009); the
OpenAPI contract is built by ``app/core/openapi.py``. Routers of ``app/api`` are contract stubs
until their tasks land. ``AuditMiddleware`` writes changing actions and rejected agent requests
to ``audit_log`` (``app/auth/audit.py``, ADR-008); ``RateLimitMiddleware`` bounds how often one
agent may call (``app/core/ratelimit.py``, T-51).
"""

from datetime import UTC, datetime

from app import __version__
from app.api import API_PREFIX, api_router
from app.auth.audit import AuditMiddleware
from app.core.errors import register_error_handlers
from app.core.openapi import ContractApp, operation_id
from app.core.ratelimit import RateLimitMiddleware
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
    application.add_middleware(AuditMiddleware)
    # Added last, so it wraps the audit: a request over the limit is refused before routing and
    # writes the record of its refusal itself (``app/core/ratelimit.py``, T-51).
    application.add_middleware(RateLimitMiddleware)

    @application.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Liveness probe: server is up; the time is UTC (ADR-014)."""
        return HealthResponse(status="ok", version=__version__, time=datetime.now(UTC))

    application.include_router(api_router)
    return application


app = create_app()
