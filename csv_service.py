from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import logging
from io import BytesIO
from test_ocr import run_ocr_on_pdf, results_to_dataframe

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("csv_service")

app = FastAPI(title="OCR CSV Service")

@app.post("/ocr/csv")
async def ocr_csv(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
):
    """OCR endpoint streaming CSV output."""
    pdf_bytes = await file.read()
    logger.info(f"OCR CSV request for pages {start_page}-{end_page}")
    try:
        # Run OCR and convert to DataFrame
        results_json, _ = run_ocr_on_pdf(pdf_bytes, start_page, end_page)
        df, _ = results_to_dataframe(results_json)
    except Exception as e:
        logger.error(f"Error in OCR processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if df.empty:
        logger.warning("No data to convert to CSV")
        raise HTTPException(status_code=400, detail="No data to convert to CSV")

    # Stream DataFrame to CSV
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig")
    buffer = BytesIO(csv_bytes.encode("utf-8-sig"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ocr_results.csv"}
    )
