from fastapi import APIRouter, Query, HTTPException
from app.core.config import load_db_config
from app.core.database import create_pg_engine
from sqlalchemy import text

router = APIRouter()

@router.get("/ping-db")
def ping_db(empresa: str = Query(...)):
    try:
        config = load_db_config(empresa)
        engine = create_pg_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "success", "message": f"Conexión exitosa a la base de datos de {empresa}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de conexión: {e}")
