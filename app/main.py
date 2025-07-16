from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.web import router as web_router  # 👈 nuevo router

app = FastAPI(title="Excel Upload API")

# API routes
app.include_router(upload_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")

# Web form routes (sin prefijo para que / sea la raíz)
app.include_router(web_router)
