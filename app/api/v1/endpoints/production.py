from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.logger import get_logger
from app.schemas import ErrorResponse, OperationResponse
from app.services.production_processor import process_production_and_update_db
from app.utils.file_validation import validate_xlsx_filename
from app.validation import ExcelValidationError

router = APIRouter(tags=["production"])
logger = get_logger(__name__)


@router.post(
    "/production/upload",
    response_model=OperationResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def upload_production(
    company: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        validate_xlsx_filename(file.filename)

        logger.info("Processing production upload", extra={"company": company, "upload_filename": file.filename})
        result = await run_in_threadpool(process_production_and_update_db, file, company)
        logger.info("Production upload processed", extra={"company": company, "warnings": len(result.warnings)})
        return {"status": "success", "message": result.message, "warnings": result.warnings}
    except ExcelValidationError as e:
        logger.warning("Validation failed on production upload", extra={"company": company, "errors": [i.message for i in e.issues]})
        raise HTTPException(status_code=400, detail=[i.message for i in e.issues]) from e
    except ValueError as e:
        logger.warning("Bad production upload", extra={"company": company, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Unexpected error processing production upload", extra={"company": company})
        raise HTTPException(status_code=500, detail="Internal server error") from None
