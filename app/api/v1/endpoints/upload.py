from fastapi import APIRouter, Request, HTTPException
<<<<<<< HEAD

=======
>>>>>>> 357370a3a9a0814e08bbbd86fd015436512dc053
from app.services.excel_processor import process_excel_and_update_db
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload/")
<<<<<<< HEAD
@router.post("/well-configuration/")
async def upload_well_configuration(request: Request):
    try:
        form = await request.form()
        company = form.get("company")
        lift_method = form.get("lift_method")
        file = form.get("file[0]") or form.get("file")  # keep compatibility if the frontend sends file[0]

        if not company or not lift_method or not file:
            logger.warning("Missing fields or file on upload request", extra={"company": company, "lift_method": lift_method})
            raise HTTPException(status_code=400, detail="Missing fields or file.")

        if not file.filename.lower().endswith(".xlsx"):
            logger.warning("Rejected non-xlsx file", extra={"company": company, "filename": file.filename})
            raise HTTPException(status_code=400, detail="File must be .xlsx")

        lift = lift_method.upper()
        if lift not in {"ESP", "GL"}:
            logger.warning("Invalid lift method", extra={"company": company, "lift_method": lift_method})
            raise HTTPException(status_code=400, detail="Lift method must be 'ESP' or 'GL'")

        logger.info("Processing well configuration upload", extra={"company": company, "lift_method": lift, "filename": file.filename})
        result = process_excel_and_update_db(file, company, lift)
        logger.info("Well configuration upload processed", extra={"company": company, "lift_method": lift, "result": result})
        return {"status": "success", "message": result}

    except HTTPException:
        raise
=======
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

>>>>>>> 357370a3a9a0814e08bbbd86fd015436512dc053
    except Exception as e:
        logger.exception("Unexpected error processing upload", extra={"company": company, "lift_method": lift_method})
        raise HTTPException(status_code=500, detail=str(e))
