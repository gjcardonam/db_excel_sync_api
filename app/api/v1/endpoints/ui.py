from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.logger import get_logger
from app.services.excel_processor import process_excel_and_update_db
from app.services.wellheader_updater import update_wellheader_from_excel

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = get_logger(__name__)


@router.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.get("/well-configuration", response_class=HTMLResponse)
async def render_upload_page(request: Request):
    return templates.TemplateResponse(request, "upload.html", {"message": ""})


@router.post("/well-configuration/process", response_class=HTMLResponse)
async def process_excel(
    request: Request,
    company: str = Form(...),
    lift_method: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return templates.TemplateResponse(request, "upload.html", {"message": "File must be .xlsx."})

        lift = lift_method.upper()
        if lift not in {"ESP", "GL"}:
            return templates.TemplateResponse(request, "upload.html", {"message": "Lift method must be 'ESP' or 'GL'."})

        logger.info("Processing well configuration via UI", extra={"company": company, "lift_method": lift, "upload_filename": file.filename})
        result = await run_in_threadpool(process_excel_and_update_db, file, company, lift)
        logger.info("Well configuration processed via UI", extra={"company": company, "lift_method": lift, "result": result})
        return templates.TemplateResponse(request, "upload.html", {"message": f"Success: {result}"})

    except ValueError as e:
        logger.warning("Validation error processing well configuration via UI", extra={"company": company, "lift_method": lift_method, "error": str(e)})
        return templates.TemplateResponse(request, "upload.html", {"message": str(e)})
    except Exception:
        logger.exception("Error processing well configuration via UI", extra={"company": company, "lift_method": lift_method})
        return templates.TemplateResponse(request, "upload.html", {"message": "An unexpected error occurred. Please try again or contact support."})


@router.get("/wellheader", response_class=HTMLResponse)
async def render_wellheader_page(request: Request):
    return templates.TemplateResponse(request, "wellheader_upload.html", {"message": ""})


@router.post("/wellheader/process", response_class=HTMLResponse)
async def process_wellheader(
    request: Request,
    company: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return templates.TemplateResponse(request, "wellheader_upload.html", {"message": "File must be .xlsx."})

        logger.info("Processing wellheader via UI", extra={"company": company, "upload_filename": file.filename})
        result = await run_in_threadpool(update_wellheader_from_excel, file, company, "WELLHEADER")
        logger.info("Wellheader processed via UI", extra={"company": company, "result": result})
        return templates.TemplateResponse(request, "wellheader_upload.html", {"message": f"Success: {result}"})
    except Exception:
        logger.exception("Error processing wellheader via UI", extra={"company": company})
        return templates.TemplateResponse(request, "wellheader_upload.html", {"message": "An unexpected error occurred. Please try again or contact support."})
