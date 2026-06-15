from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.core.logger import get_logger
from app.schemas import ErrorResponse, OperationResponse
from app.services.excel_processor import process_excel_and_update_db
from app.utils.file_validation import validate_xlsx_filename
from app.validation import ExcelValidationError

router = APIRouter(tags=["well-configuration"])
logger = get_logger(__name__)


@router.post(
    "/well-configuration/",
    response_model=OperationResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def upload_well_configuration(request: Request):
    company = lift_method = None
    try:
        form = await request.form()
        company = form.get("company")
        lift_method = form.get("lift_method")
        # Accept file[0] for backward compatibility with frontends that send it.
        file = form.get("file[0]") or form.get("file")

        if not company or not lift_method or not file:
            logger.warning("Missing fields or file on upload request", extra={"company": company, "lift_method": lift_method})
            raise HTTPException(status_code=400, detail="Missing fields or file.")

        validate_xlsx_filename(getattr(file, "filename", None))

        lift = lift_method.upper()
        if lift not in {"ESP", "GL"}:
            logger.warning("Invalid lift method", extra={"company": company, "lift_method": lift_method})
            raise HTTPException(status_code=400, detail="Lift method must be 'ESP' or 'GL'")

        logger.info("Processing well configuration upload", extra={"company": company, "lift_method": lift, "upload_filename": file.filename})
        # Heavy, blocking work (pandas + psycopg2) runs in a worker thread so it
        # does not block the async event loop.
        result = await run_in_threadpool(process_excel_and_update_db, file, company, lift)
        logger.info("Well configuration upload processed", extra={"company": company, "lift_method": lift, "warnings": len(result.warnings)})
        return {"status": "success", "message": result.message, "warnings": result.warnings}

    except HTTPException:
        raise
    except ExcelValidationError as e:
        logger.warning("Validation failed on upload", extra={"company": company, "lift_method": lift_method, "errors": [i.message for i in e.issues]})
        raise HTTPException(status_code=400, detail=[i.message for i in e.issues]) from e
    except ValueError as e:
        logger.warning("Bad upload", extra={"company": company, "lift_method": lift_method, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Unexpected error processing upload", extra={"company": company, "lift_method": lift_method})
        raise HTTPException(status_code=500, detail="Internal server error") from None
