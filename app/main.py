from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.production import router as production_router
from app.api.v1.endpoints.ui import router as ui_router
from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.wellheader import router as wellheader_router
from app.api.v1.endpoints.wellheader_insert import router as wellheader_insert_router
from app.core.database import dispose_all_engines
from app.core.logger import get_logger, setup_logging
from app.core.settings import settings

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup: routers registered.")
    yield
    # Shutdown: release pooled DB connections cleanly.
    dispose_all_engines()
    logger.info("Application shutdown: database engines disposed.")


app = FastAPI(
    title="Well Configuration API",
    description="Internal API to sync well configuration and wellheader data "
    "from Excel files into per-company Postgres databases.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", extra={"path": request.url.path, "method": request.method})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Reject oversized request bodies early (based on Content-Length)."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.MAX_UPLOAD_BYTES:
                logger.warning("Rejected oversized request", extra={"path": request.url.path, "content_length": content_length})
                return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        except ValueError:
            pass
    return await call_next(request)


# CORS middleware.
# Origins are configurable via CORS_ALLOW_ORIGINS (comma-separated). Credentials
# are disabled because this API has no cookie/session auth, and the wildcard origin
# combined with allow_credentials=True is rejected by browsers anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(upload_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(wellheader_router, prefix="/api/v1")
app.include_router(wellheader_insert_router, prefix="/api/v1")
app.include_router(production_router, prefix="/api/v1")
app.include_router(ui_router)
