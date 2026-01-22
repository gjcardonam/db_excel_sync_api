from fastapi import APIRouter, Form, UploadFile, File, HTTPException

from app.services.wellheader_updater import update_wellheader_from_excel
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/wellheader/upload")
async def upload_wellheader(
    company: str = Form(...),
    sheet_name: str = Form("WELLHEADER"),
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith(".xlsx"):
        logger.warning("Rejected non-xlsx file for wellheader upload", extra={"company": company, "filename": file.filename})
        raise HTTPException(status_code=400, detail="File must be .xlsx")

    try:
        logger.info("Processing wellheader upload", extra={"company": company, "sheet": sheet_name, "filename": file.filename})
        msg = update_wellheader_from_excel(file, company, sheet_name)
        logger.info("Wellheader upload processed", extra={"company": company, "sheet": sheet_name, "result": msg})
        return {"status": "success", "message": msg}
    except ValueError as e:
        logger.warning("Validation error on wellheader upload", extra={"company": company, "sheet": sheet_name, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error processing wellheader upload", extra={"company": company, "sheet": sheet_name})
        raise HTTPException(status_code=500, detail=str(e))
