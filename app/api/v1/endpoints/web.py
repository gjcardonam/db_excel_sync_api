from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.excel_processor import process_excel_and_update_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def form_get(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload-form", response_class=HTMLResponse)
async def form_post(
    request: Request,
    empresa: str = Form(...),
    produccion: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Llamada directa al servicio (evita cuelgue)
        result = process_excel_and_update_db(file, empresa, produccion.upper())
        msg = f"✅ {result}"
    except Exception as e:
        msg = f"❌ Error al procesar: {e}"

    return templates.TemplateResponse("upload.html", {"request": request, "message": msg})
