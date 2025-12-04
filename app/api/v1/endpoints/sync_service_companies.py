from fastapi import APIRouter, Request, HTTPException
from app.services.sync_service_companies_grafana import sync_service_companies_grafana

router = APIRouter()

@router.put("/sync/")
async def sync_service_companies(request: Request):
    try:
        form = await request.form()
        empresa = form.get("empresa")

        if not empresa:
            raise HTTPException(status_code=400, detail="Faltan campos o archivo")

        result = sync_service_companies_grafana(empresa=empresa)
        return {"status": "success", "message": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
