from fastapi import APIRouter, Request, HTTPException
from app.services.sync_service_companies_grafana import sync_service_companies_grafana
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.put("/sync/")
async def sync_service_companies(request: Request):
    try:
        form = await request.form()
        empresa = form.get("empresa")

        if not empresa:
            raise HTTPException(status_code=400, detail="Missing required field: empresa")

        logger.info("Syncing service companies", extra={"empresa": empresa})
        result = sync_service_companies_grafana(empresa=empresa)
        logger.info("Service companies sync completed", extra={"empresa": empresa})
        return {"status": "success", "message": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error syncing service companies")
        raise HTTPException(status_code=500, detail="Internal server error")
