
from fastapi import FastAPI, UploadFile, File, HTTPException
from services.processing_service import process_excel_and_update_db

app = FastAPI()

@app.post("/upload/")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xlsx")

    try:
        result = process_excel_and_update_db(file)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
