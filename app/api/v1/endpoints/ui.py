from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.excel_processor import process_excel_and_update_db
from app.services.wellheader_updater import update_wellheader_from_excel
from app.core.logger import get_logger

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = get_logger(__name__)


@router.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/upload", response_class=HTMLResponse)
@router.get("/well-configuration", response_class=HTMLResponse)
async def render_upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request, "message": ""})


@router.post("/process", response_class=HTMLResponse)
@router.post("/well-configuration/process", response_class=HTMLResponse)
async def process_excel(
    request: Request,
    company: str = Form(...),
    lift_method: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return templates.TemplateResponse("upload.html", {"request": request, "message": "File must be .xlsx."})

        lift = lift_method.upper()
        if lift not in {"ESP", "GL"}:
            return templates.TemplateResponse("upload.html", {"request": request, "message": "Lift method must be 'ESP' or 'GL'."})

        logger.info("Processing well configuration via UI", extra={"company": company, "lift_method": lift, "filename": file.filename})
        result = process_excel_and_update_db(file, company, lift)
        logger.info("Well configuration processed via UI", extra={"company": company, "lift_method": lift, "result": result})
        return templates.TemplateResponse("upload.html", {"request": request, "message": f"Success: {result}"})

    except Exception as e:
        logger.exception("Error processing well configuration via UI", extra={"company": company, "lift_method": lift_method})
        return templates.TemplateResponse("upload.html", {"request": request, "message": f"Error: {str(e)}"})


@router.get("/wellheader", response_class=HTMLResponse)
async def render_wellheader_page(request: Request):
    return templates.TemplateResponse("wellheader_upload.html", {"request": request, "message": ""})


@router.post("/wellheader/process", response_class=HTMLResponse)
async def process_wellheader(
    request: Request,
    company: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return templates.TemplateResponse("wellheader_upload.html", {"request": request, "message": "File must be .xlsx."})

        logger.info("Processing wellheader via UI", extra={"company": company, "upload_filename": file.filename})
        result = update_wellheader_from_excel(file, company, "WELLHEADER")
        logger.info("Wellheader processed via UI", extra={"company": company, "result": result})
        return templates.TemplateResponse("wellheader_upload.html", {"request": request, "message": f"Success: {result}"})
    except Exception as e:
        logger.exception("Error processing wellheader via UI", extra={"company": company})
        return templates.TemplateResponse("wellheader_upload.html", {"request": request, "message": f"Error: {str(e)}"})
