from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.excel_processor import process_excel_and_update_db

router = APIRouter()

@router.post("/upload/")
async def upload_excel(
    file: UploadFile = File(...),
    empresa: str = Query(...),
    produccion: str = Query(...)
):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xlsx")

    if produccion.upper() not in {"ESP", "GL"}:
        raise HTTPException(status_code=400, detail="Producción debe ser 'ESP' o 'GL'")

    try:
        result = process_excel_and_update_db(file, empresa, produccion.upper())
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
