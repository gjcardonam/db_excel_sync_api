from fastapi import APIRouter, Request, HTTPException
from app.services.excel_processor import process_excel_and_update_db

router = APIRouter()

@router.post("/upload/")
async def upload_excel(request: Request):
    try:
        form = await request.form()
        empresa = form.get("empresa")
        produccion = form.get("produccion")
        file = form.get("file[0]")  # 👈 importante si el frontend envía así el nombre

        if not empresa or not produccion or not file:
            raise HTTPException(status_code=400, detail="Faltan campos o archivo")

        if not file.filename.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="El archivo debe ser .xlsx")

        if produccion.upper() not in {"ESP", "GL"}:
            raise HTTPException(status_code=400, detail="Producción debe ser 'ESP' o 'GL'")

        result = process_excel_and_update_db(file, empresa, produccion.upper())
        return {"status": "success", "message": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
