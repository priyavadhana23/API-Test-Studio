"""
web_dashboard/backend/main.py
==============================
FastAPI application entry point for API Test Studio.

Start the server:
    # from the API_Test_Studio/ directory:
    ../.venv/bin/uvicorn web_dashboard.backend.main:app --reload --port 8000

Or use the helper at the bottom:
    ../.venv/bin/python web_dashboard/backend/main.py

Docs (once running):
    Swagger UI  →  http://127.0.0.1:8000/docs
    ReDoc       →  http://127.0.0.1:8000/redoc
    OpenAPI JSON→  http://127.0.0.1:8000/openapi.json
    Health      →  http://127.0.0.1:8000/api/health
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# ── Ensure the framework packages are importable regardless of cwd ──────────
_BACKEND_DIR = Path(__file__).resolve().parent          # web_dashboard/backend/
_PROJECT_ROOT = _BACKEND_DIR.parent.parent              # API_Test_Studio/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from web_dashboard.backend.config.settings import get_settings
from web_dashboard.backend.middleware.logging_middleware import LoggingMiddleware
from web_dashboard.backend.routers import health as health_router
from web_dashboard.backend.schemas.common import ErrorDetail


# ---------------------------------------------------------------------------
# Bootstrap — run once at startup
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    """
    Initialise the framework logger before FastAPI creates any handlers.

    Reuses the existing LoggerFactory so all log output — from framework
    modules AND from FastAPI routes — flows through the same handlers.
    """
    settings = get_settings()
    from utilities.logger import LoggerFactory
    LoggerFactory.initialize(settings.logging_cfg, project_root=_PROJECT_ROOT)


_bootstrap()

from utilities.logger import get_logger
logger = get_logger("web_dashboard.backend")


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup and shutdown; could seed shared state here in future."""
    settings = get_settings()
    logger.info(
        "API Test Studio backend starting — %s v%s  [%s:%d]",
        settings.app_name,
        settings.app_version,
        settings.host,
        settings.port,
    )
    logger.info("Database : %s", settings.db_path)
    logger.info("Reports  : %s", settings.reports_dir)
    logger.info("Docs     : http://%s:%d/docs", settings.host, settings.port)
    yield
    logger.info("API Test Studio backend shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**API Test Studio** — Enterprise API Testing Platform\n\n"
        "This backend exposes the testing framework over a REST API, enabling "
        "external tools, dashboards, and CI/CD pipelines to trigger test runs, "
        "retrieve results, and generate reports programmatically.\n\n"
        "**Phase 9.2** — Synchronous pipeline: specs upload, execution, run history, analytics, reports.\n"
        "**Phase 9.3** — Async job queue: non-blocking `POST /api/jobs` with status polling.\n"
        "**Phase 9.4** — Test-results query: filter/search/paginate individual test-case results."
    ),
    contact={
        "name": "API Test Studio",
        "url":  "https://github.com/your-org/api-test-studio",
    },
    license_info={"name": "MIT"},
    openapi_tags=[
        {
            "name": "System",
            "description": "Health checks and service identity.",
        },
        {
            "name": "Specifications",
            "description": "Upload and manage API specification files. *(Phase 9.2)*",
        },
        {
            "name": "Execution",
            "description": "Trigger and monitor test runs. *(Phase 9.3)*",
        },
        {
            "name": "Results",
            "description": "Query test-case results and validation details. *(Phase 9.4)*",
        },
        {
            "name": "Reports",
            "description": "Generate and download HTML/PDF/CSV reports. *(Phase 9.5)*",
        },
        {
            "name": "Analytics",
            "description": "Access analytics summaries and health scores. *(Phase 9.6)*",
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware  (order matters — outermost wraps innermost)
# ---------------------------------------------------------------------------

# 1. CORS — must be first so preflight OPTIONS requests are handled before
#    any other middleware inspects them.
#
#    allow_origins covers the explicit list from settings (localhost + the
#    production Vercel domain).
#
#    allow_origin_regex additionally permits every Vercel preview deployment
#    URL (e.g. https://api-test-studio-abc123-org.vercel.app) without
#    enumerating them, since each preview gets a unique subdomain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request logging + timing
app.add_middleware(LoggingMiddleware)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content=ErrorDetail(
            error="invalid_input",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    logger.warning("KeyError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=404,
        content=ErrorDetail(
            error="not_found",
            message=f"Resource not found: {exc}",
        ).model_dump(),
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    logger.error("RuntimeError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error="internal_error",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled %s on %s %s: %s",
        type(exc).__name__, request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error="internal_error",
            message="An unexpected error occurred.",
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

_STATIC_DIR = _BACKEND_DIR / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router.router)

# ── Router registration order matters for path disambiguation ───────────────
#
# FastAPI matches routes in registration order.  Rules applied here:
#   1. More-specific literal paths beat wildcard {param} paths at the same
#      prefix level.  So /api/jobs must come BEFORE /api/runs/{run_id}.
#   2. Nested result paths (/api/runs/{run_id}/results/...) must come BEFORE
#      the bare /api/runs/{run_id} catch-all.
#
# Order:
#   specs      — /api/specifications/...   (no conflicts)
#   jobs       — /api/jobs, /api/jobs/{job_id}   ← BEFORE runs/{run_id}
#   results    — /api/runs/{run_id}/results/...  ← BEFORE bare runs/{run_id}
#   runs       — /api/run, /api/runs, /api/runs/{run_id}
#   analytics  — /api/analytics/...
#   reports    — /api/reports/...

from web_dashboard.backend.routers import specs as specs_router
from web_dashboard.backend.routers import jobs as jobs_router
from web_dashboard.backend.routers import results as results_router
from web_dashboard.backend.routers import runs as runs_router
from web_dashboard.backend.routers import analytics as analytics_router
from web_dashboard.backend.routers import reports as reports_router

app.include_router(specs_router.router)      # Phase 9.2
app.include_router(jobs_router.router)       # Phase 9.3 — before runs/{run_id}
app.include_router(results_router.router)    # Phase 9.4 — before runs/{run_id}
app.include_router(runs_router.router)       # Phase 9.2
app.include_router(analytics_router.router)  # Phase 9.2
app.include_router(reports_router.router)    # Phase 9.2


# ---------------------------------------------------------------------------
# Dev-mode entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    s = get_settings()
    uvicorn.run(
        "web_dashboard.backend.main:app",
        host=s.host,
        port=s.port,
        reload=s.reload,
        log_level=s.log_level,
    )
