from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.web import router as web_router

app = FastAPI(title="Excel Upload API")

# Rutas de API
app.include_router(upload_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")

# Ruta para formulario web
app.include_router(web_router)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
