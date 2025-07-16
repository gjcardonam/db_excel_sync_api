from fastapi import FastAPI
from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.health import router as health_router 

app = FastAPI(title="Excel Upload API")

app.include_router(upload_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1") 