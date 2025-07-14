from fastapi import FastAPI
from app.api.v1.endpoints.upload import router as upload_router

app = FastAPI(title="Excel Upload API")

app.include_router(upload_router, prefix="/api/v1")
