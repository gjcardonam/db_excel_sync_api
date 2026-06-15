from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.ui import router as ui_router
from app.api.v1.endpoints.wellheader import router as wellheader_router
from app.core.logger import setup_logging, get_logger
from app.core.settings import settings

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Well Configuration API")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", extra={"path": request.url.path, "method": request.method})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Rutas de API
app.include_router(upload_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(wellheader_router, prefix="/api/v1")
app.include_router(ui_router)

logger.info("Application startup: routers registered.")

# CORS middleware.
# Origins are configurable via CORS_ALLOW_ORIGINS (comma-separated). Credentials
# are disabled because this API has no cookie/session auth, and the wildcard origin
# combined with allow_credentials=True is rejected by browsers anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
