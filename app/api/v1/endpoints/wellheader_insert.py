from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.logger import get_logger
from app.schemas import ErrorResponse, OperationResponse
from app.services.wellheader_loader import insert_wellheader_from_excel
from app.utils.file_validation import validate_xlsx_filename
from app.validation import ExcelValidationError

router = APIRouter(tags=["wellheader-insert"])
logger = get_logger(__name__)


@router.post(
    "/wellheader/insert",
    response_model=OperationResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def insert_wellheader(
    company: str = Form(...),
    sheet_name: str = Form("WELLHEADER"),
    file: UploadFile = File(...),
):
    try:
        validate_xlsx_filename(file.filename)

        logger.info("Processing wellheader insert", extra={"company": company, "sheet": sheet_name, "upload_filename": file.filename})
        result = await run_in_threadpool(insert_wellheader_from_excel, file, company, sheet_name)
        logger.info("Wellheader insert processed", extra={"company": company, "sheet": sheet_name, "warnings": len(result.warnings)})
        return {"status": "success", "message": result.message, "warnings": result.warnings}
    except ExcelValidationError as e:
        logger.warning("Validation failed on wellheader insert", extra={"company": company, "sheet": sheet_name, "errors": [i.message for i in e.issues]})
        raise HTTPException(status_code=400, detail=[i.message for i in e.issues]) from e
    except ValueError as e:
        logger.warning("Bad wellheader insert", extra={"company": company, "sheet": sheet_name, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Unexpected error processing wellheader insert", extra={"company": company, "sheet": sheet_name})
        raise HTTPException(status_code=500, detail="Internal server error") from None
