from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

from app.core.config import load_db_config
from app.core.database import create_pg_engine
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/ping-db")
def ping_db(company: str = Query(...)):
    try:
        logger.info("DB ping requested", extra={"company": company})
        config = load_db_config(company)
        engine = create_pg_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB ping successful", extra={"company": company})
        return {"status": "success", "message": f"Successful database connection for {company}"}
    except Exception as e:
        logger.exception("DB ping failed", extra={"company": company})
        raise HTTPException(status_code=500, detail=f"Database connection failed for {company}")
