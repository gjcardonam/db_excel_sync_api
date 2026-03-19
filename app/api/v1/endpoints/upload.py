from fastapi import APIRouter, Request, HTTPException
from app.services.excel_processor import process_excel_and_update_db
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

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
    except ValueError as e:
        logger.warning("Validation error on upload", extra={"company": company, "lift_method": lift_method, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error processing upload", extra={"company": company, "lift_method": lift_method})
        raise HTTPException(status_code=500, detail="Internal server error")
