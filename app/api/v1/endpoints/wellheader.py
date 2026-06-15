from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.logger import get_logger
from app.schemas import ErrorResponse, OperationResponse
from app.services.wellheader_updater import update_wellheader_from_excel

router = APIRouter(tags=["wellheader"])
logger = get_logger(__name__)


@router.post(
    "/wellheader/upload",
    response_model=OperationResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def upload_wellheader(
    company: str = Form(...),
    sheet_name: str = Form("WELLHEADER"),
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".xlsx"):
        logger.warning("Rejected non-xlsx file for wellheader upload", extra={"company": company, "upload_filename": file.filename})
        raise HTTPException(status_code=400, detail="File must be .xlsx")

    try:
        logger.info("Processing wellheader upload", extra={"company": company, "sheet": sheet_name, "upload_filename": file.filename})
        # Run blocking pandas/DB work off the event loop.
        msg = await run_in_threadpool(update_wellheader_from_excel, file, company, sheet_name)
        logger.info("Wellheader upload processed", extra={"company": company, "sheet": sheet_name, "result": msg})
        return {"status": "success", "message": msg}
    except ValueError as e:
        logger.warning("Validation error on wellheader upload", extra={"company": company, "sheet": sheet_name, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Unexpected error processing wellheader upload", extra={"company": company, "sheet": sheet_name})
        raise HTTPException(status_code=500, detail="Internal server error") from None
