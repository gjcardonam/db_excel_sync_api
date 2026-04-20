from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.ui import router as ui_router
from app.api.v1.endpoints.wellheader import router as wellheader_router
from app.api.v1.endpoints.clickup import router as clickup_router
from app.core.logger import setup_logging, get_logger

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
app.include_router(clickup_router, prefix="/api/v1")
app.include_router(ui_router)

logger.info("Application startup: routers registered.")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
