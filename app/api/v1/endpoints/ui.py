from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.logger import get_logger
from app.services.excel_processor import process_excel_and_update_db
from app.services.wellheader_updater import update_wellheader_from_excel
from app.utils.file_validation import validate_xlsx_filename
from app.validation import ExcelValidationError

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = get_logger(__name__)


def _render(request, template, *, success=None, warnings=None, validation=None, error=None):
    """Render a page with a consistent feedback context.

    - error      -> RED   (technical/system failure)
    - validation -> ORANGE (data/file problems the user must fix; upload not applied)
    - warnings   -> ORANGE (non-blocking notes; shown alongside a success)
    - success    -> GREEN
    """
    return templates.TemplateResponse(
        request,
        template,
        {
            "success": success,
            "warnings": warnings or [],
            "validation": validation or [],
            "error": error,
        },
    )


@router.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.get("/well-configuration", response_class=HTMLResponse)
async def render_upload_page(request: Request):
    return _render(request, "upload.html")


@router.post("/well-configuration/process", response_class=HTMLResponse)
async def process_excel(
    request: Request,
    company: str = Form(...),
    lift_method: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        validate_xlsx_filename(file.filename)

        lift = lift_method.upper()
        if lift not in {"ESP", "GL"}:
            return _render(request, "upload.html", validation=["Lift method must be 'ESP' or 'GL'."])

        logger.info("Processing well configuration via UI", extra={"company": company, "lift_method": lift, "upload_filename": file.filename})
        result = await run_in_threadpool(process_excel_and_update_db, file, company, lift)
        return _render(request, "upload.html", success=result.message, warnings=result.warnings)

    except ExcelValidationError as e:
        logger.warning("Validation failed via UI", extra={"company": company, "errors": [i.message for i in e.issues]})
        return _render(request, "upload.html", validation=[i.message for i in e.issues])
    except ValueError as e:
        logger.warning("Bad upload via UI", extra={"company": company, "error": str(e)})
        return _render(request, "upload.html", validation=[str(e)])
    except Exception:
        logger.exception("Error processing well configuration via UI", extra={"company": company})
        return _render(request, "upload.html", error="An unexpected error occurred. Please try again or contact support.")


@router.get("/wellheader", response_class=HTMLResponse)
async def render_wellheader_page(request: Request):
    return _render(request, "wellheader_upload.html")


@router.post("/wellheader/process", response_class=HTMLResponse)
async def process_wellheader(
    request: Request,
    company: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        validate_xlsx_filename(file.filename)

        logger.info("Processing wellheader via UI", extra={"company": company, "upload_filename": file.filename})
        result = await run_in_threadpool(update_wellheader_from_excel, file, company, "WELLHEADER")
        return _render(request, "wellheader_upload.html", success=result.message, warnings=result.warnings)

    except ExcelValidationError as e:
        logger.warning("Validation failed on wellheader via UI", extra={"company": company, "errors": [i.message for i in e.issues]})
        return _render(request, "wellheader_upload.html", validation=[i.message for i in e.issues])
    except ValueError as e:
        logger.warning("Bad wellheader upload via UI", extra={"company": company, "error": str(e)})
        return _render(request, "wellheader_upload.html", validation=[str(e)])
    except Exception:
        logger.exception("Error processing wellheader via UI", extra={"company": company})
        return _render(request, "wellheader_upload.html", error="An unexpected error occurred. Please try again or contact support.")
