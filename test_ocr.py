import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
import requests
import base64
import json
import re
import pandas as pd
import ast
import time
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
HEADERS = {'Content-Type': 'application/json'}

PROMPT = """
You are an expert AI assistant specialized in comprehensive and highly accurate document data extraction. Your primary task is to process tax invoices with inconsistent and challenging layouts and extract ALL available information.

**Challenge:** The documents have variable layouts. Information is often split across lines, and corresponding labels and values can be spatially distant. Simple OCR or fixed-template methods will fail. You must use contextual and spatial understanding to succeed.

**Extraction Strategy (Hybrid Approach):**

Your goal is to extract information into a structured JSON object for each invoice. We will use a hybrid approach:
1.  **Core Fields:** Extract the most critical information into a predefined structure.
2.  **Additional Data:** Capture every other piece of data on the page as generic key-value pairs.
3.  **Line Items:** Dynamically extract all columns from the line item tables.

**JSON Output Schema and Instructions:**

**1. Core Information (Primary Fields):**
   - Extract these into the top level of the JSON object.
   - `document_type`: "ใบกำกับภาษี/Tax Invoice", "ใบเสร็จรับเงิน/Receipt", etc.
   - `tax_invoice_number`: The main invoice number.
   - `tax_invoice_date`: The primary date of the invoice.
   - `vendor_name`, `vendor_tax_id`, `vendor_address`: Full details of the invoice issuer.
   - `customer_name`, `customer_tax_id`, `customer_address`: Full details of the recipient.
   - `sub_total`, `vat_amount`, `grand_total`: The main financial summary.

**2. Line Items (Comprehensive Table Extraction):**
   - `line_items`: This must be an array of objects.
   - For each invoice, identify the main table of products or services.
   - Normalize column names using the following standard keys:
     - `No.` → Item number if available
     - `Description` → Product or service name/description
     - `Quantity` → Amount or unit count
     - `Unit Price` → Price per unit
     - `Amount` → Total for that line
   - Use these exact key names even if the original table headers are in Thai or vary in wording.
   - If a row doesn't contain a value for one of these fields, include the key with a `null` value.
   
**3. Document Checks:**
   - After extracting all data, scan the image to determine the presence of:
     - `has_tax_invoice`: true if the document contains any clear indication (text or title) that it is a tax invoice, such as the phrase "ใบกำกับภาษี".
     - `has_signature`: true if there is a visible signature or a signature-like scribble/stamp in the document.
   

**Example JSON Output (Illustrating the Hybrid Structure):**

```json
{
  "document_type": "ใบกำกับภาษี/Tax Invoice",
  "tax_invoice_number": "4104085",
  "tax_invoice_date": "04/01/25",
  "vendor_name": "RICOH SERVICES (THAILAND) LIMITED",
  "vendor_tax_id": "0105531026179",
  "vendor_address": "341 Onnuj Road, Kwaeng Prawet, Khet Prawet, Bangkok 10250",
  "customer_name": "บริษัท แมงโก้ คอนซัลแตนท์ จำกัด",
  "customer_tax_id": "0105551067687",
  "customer_address": "เลขที่ 555 อาคารรสา ทาวเวอร์ 1 ยูนิต 2304-1 ชั้นที่ 23 ถนนพหลโยธิน แขวงจตุจักร เขตจตุจักร กรุงเทพมหานคร 10900",
  "line_items": [
    {
      "รายละเอียด / Description": "ค่าเช่า/Rental Charge",
      "จำนวนเงิน / Amount": 3000.00
    }
  ],
  "sub_total": 3000.00,
  "vat_amount": 210.00,
  "grand_total": 3210.00,
  "tax_invoice": true,
  "authorized_signature": true
}
"""

def convert_pdf_to_images(pdf_bytes, dpi=300):
    """Convert PDF bytes to list of PIL Images."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        images.append(Image.open(BytesIO(pix.tobytes("png"))))
    return images

def fix_numeric_commas(json_str):
    """Remove commas in numeric values before JSON parsing."""
    def repl(m):
        key, num = m.group(1), m.group(2).replace(',', '')
        return f'{key}: {num}'
    return re.sub(r'(".*?")\s*:\s*(-?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)', repl, json_str)

def extract_and_clean_json(text):
    """Extract JSON block from model output, clean, and parse."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(r"(\{.*?\})", text, re.DOTALL)
    if not match:
        return None
    raw = fix_numeric_commas(match.group(1))
    raw = re.sub(r",\s*(\}|\])", r"\1", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def run_ocr_on_pdf(pdf_bytes, start_page, end_page):
    """
    Run OCR on given page range, returning list of JSON results sequentially.
    """
    images = convert_pdf_to_images(pdf_bytes)
    selected = images[start_page - 1:end_page]
    total = len(selected)
    print(f"Processing {total} pages sequentially")
    all_results = []

    for idx, img in enumerate(selected, start=start_page):
        try:
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            payload = {
                "contents": [{
                    "parts": [
                        {"text": PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": b64}}
                    ]
                }],
                "generationConfig": {"maxOutputTokens": 8192}
            }
            print(f"Sending request for page {idx}")
            resp = requests.post(URL, headers=HEADERS, json=payload, timeout=120)
            if resp.ok:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = extract_and_clean_json(text)
                if result:
                    result['Page'] = idx
                    all_results.append(result)
                    print(f"Page {idx} done")
                else:
                    print(f"No JSON for page {idx}")
                    all_results.append({'Page': idx, 'error': 'No JSON', 'document_type': 'Error', 'tax_invoice_number': f'ERROR_{idx}'})
            else:
                err = f"HTTP {resp.status_code}"
                print(f"Page {idx} failed: {err}")
                all_results.append({'Page': idx, 'error': err, 'document_type': 'Error', 'tax_invoice_number': f'ERROR_{idx}'})
            print("Sleeping 3s")
            time.sleep(3)
        except Exception as e:
            print(f"Exception on page {idx}: {e}")
            all_results.append({'Page': idx, 'error': str(e), 'document_type': 'Error', 'tax_invoice_number': f'ERROR_{idx}'})

    print(f"Completed {len(all_results)} pages")
    return all_results, all_results

def format_page_ranges(pages):
    """Convert list of page numbers to compact range string."""
    pages = sorted({int(p) for p in pages if pd.notnull(p)})
    if not pages:
        return ""
    ranges = []
    start = end = pages[0]
    for p in pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append(str(start) if start == end else f"{start}-{end}")
            start = end = p
    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ", ".join(ranges)

def extract_first_page_number(page_str):
    """Get first page number from a range string."""
    if isinstance(page_str, str) and '-' in page_str:
        return int(page_str.split('-')[0])
    try:
        return int(page_str)
    except:
        return 0


def results_to_dataframe(all_results):
    """Convert list of result dicts to aggregated DataFrame."""
    merged = []
    for res in all_results:
        page = res.get('Page', 0)
        items = res.pop('line_items', [])
        if isinstance(items, str):
            try:
                items = ast.literal_eval(items)
            except:
                items = []
        if items:
            for item in items:
                row = {**res, **item, 'Page': page}
                merged.append(row)
        else:
            merged.append({**res, 'Page': page})

    df = pd.DataFrame(merged)
    if 'tax_invoice_number' not in df.columns:
        return pd.DataFrame(), all_results

    agg_map = {
        'Page': lambda pages: format_page_ranges(pages),
        'document_type': 'first',
        'tax_invoice_date': 'first',
        'vendor_name': 'first',
        'vendor_tax_id': 'first',
        'vendor_address': 'first',
        'customer_name': 'first',
        'customer_tax_id': 'first',
        'customer_address': 'first',
        'sub_total': 'first',
        'vat_amount': 'first',
        'grand_total': 'first',
        'has_tax_invoice': 'first',
        'has_signature': 'last'
    }

    for col in ['No.', 'Description', 'Quantity', 'Unit Price', 'Amount']:
        if col in df.columns:
            agg_map[col] = lambda x, col=col: '\n'.join(x.dropna().astype(str))

    if 'error' in df.columns:
        agg_map['error'] = lambda x: '\n'.join(x.dropna().astype(str))

    grouped = df.groupby('tax_invoice_number').agg(agg_map).reset_index()
    grouped['sort_key'] = grouped['Page'].apply(extract_first_page_number)
    grouped = grouped.sort_values('sort_key').drop(columns='sort_key')

    column_order = [
        'Page', 'document_type', 'tax_invoice_number', 'tax_invoice_date',
        'vendor_name', 'vendor_tax_id', 'vendor_address',
        'customer_name', 'customer_tax_id', 'customer_address',
        'Description', 'Quantity', 'Unit Price', 'Amount',
        'sub_total', 'vat_amount', 'grand_total',
        'has_tax_invoice', 'has_signature', 'error'
    ]
    final_cols = [c for c in column_order if c in grouped.columns]
    return grouped[final_cols], all_results
