from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from test_ocr import run_ocr_on_pdf
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("json_service")

app = FastAPI(title="OCR JSON Service")

@app.post("/ocr/json")
async def ocr_json(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
):
    """OCR endpoint returning JSON results."""
    pdf_bytes = await file.read()
    logger.info(f"OCR JSON request for pages {start_page}-{end_page}")
    try:
        results_json, _ = run_ocr_on_pdf(pdf_bytes, start_page, end_page)
        return JSONResponse(content={"results": results_json})
    except Exception as e:
        logger.error(f"Error in OCR JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))
