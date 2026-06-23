"""FastAPI application factory.

This module is the entry point for `uvicorn backend.main:app`.  The
`create_app()` factory is separated from the module-level `app` so it
can be called with isolated settings in tests.

P2-T1: app skeleton + settings + DI (settings loaded, logging configured,
       DI via FastAPI Depends in controllers/deps.py).
P2-T2: CorrelationMiddleware registered here.
P2-T9: Global exception handlers registered here — consistent error
       envelope with no stack traces exposed to callers (org comms rule).
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.controllers.applications import router as applications_router
from backend.core.logging import CorrelationMiddleware, configure_logging, get_trace_id
from backend.core.settings import Settings
from backend.schemas.application_schema import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional Settings override (used in tests).  When None
                  the default environment-based Settings are used.

    Returns:
        A fully configured FastAPI application instance.
    """
    _settings = settings or Settings()
    configure_logging(_settings.log_level)
    log = logging.getLogger(__name__)

    app = FastAPI(
        title="Consumer Loan Origination API",
        description=(
            "Agentic loan origination system powered by LangGraph and "
            "Amazon Bedrock AgentCore.  Implements the API layer (Phase 2) "
            "of the implementation plan."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware ─────────────────────────────────────────────────────────
    app.add_middleware(CorrelationMiddleware)

    # ── Routers ────────────────────────────────────────────────────────────
    app.include_router(applications_router, prefix="/api/v1")

    # ── Ops endpoints ──────────────────────────────────────────────────────
    @app.get("/health", tags=["ops"], summary="Liveness health check")
    async def health() -> dict[str, str]:
        """Return 200 OK when the process is alive."""
        return {"status": "ok"}

    # ── P2-T9: Global exception handlers ──────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Convert FastAPI HTTPException into the stable error envelope."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                **{
                    "errorCode": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "traceId": get_trace_id(),
                }
            ).model_dump(by_alias=True),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Surface the first Pydantic validation error as a user-safe message."""
        errors = exc.errors()
        first_msg: str = errors[0].get("msg", "Validation error.") if errors else "Validation error."
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                **{
                    "errorCode": "VALIDATION_ERROR",
                    "message": first_msg,
                    "traceId": get_trace_id(),
                }
            ).model_dump(by_alias=True),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unexpected exceptions, log server-side, return generic message.

        Stack traces are NEVER forwarded to callers (org security rule).
        """
        log.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                **{
                    "errorCode": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                    "traceId": get_trace_id(),
                }
            ).model_dump(by_alias=True),
        )

    log.info(
        "FastAPI application ready",
        extra={"runtime_mode": _settings.runtime_mode, "env": _settings.app_env},
    )
    return app


# Module-level app instance consumed by uvicorn / gunicorn
app = create_app()
