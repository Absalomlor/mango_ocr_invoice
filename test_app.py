import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from PyPDF2 import PdfReader
import json

# URLs for separated services
JSON_SERVICE_URL = "http://127.0.0.1:8000"
CSV_SERVICE_URL  = "http://127.0.0.1:8001"

st.set_page_config(page_title="OCR Tax Invoice", layout="wide")
st.title("OCR ใบกำกับภาษี / Tax Invoice Extractor")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ PDF", type="pdf")

if uploaded_file:
    st.success("อัปโหลดไฟล์เรียบร้อย")

    pdf_bytes = uploaded_file.read()
    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    start_page = st.number_input("เริ่มหน้าที่", min_value=1, value=1, max_value=total_pages)
    end_page   = st.number_input("ถึงหน้าที่", min_value=start_page, value=total_pages, max_value=total_pages)

    if st.button("เริ่ม OCR ผ่าน API"):
        progress_text = st.empty()
        results = []

        # OCR หน้าเดียวทีละหน้า (sequential) กับ JSON Service
        for page in range(start_page, end_page + 1):
            progress_text.info(f"กำลัง OCR หน้า {page}")
            uploaded_file.seek(0)
            pdf_bytes = uploaded_file.read()
            files = {"file": ("document.pdf", pdf_bytes, "application/pdf")}
            data  = {"start_page": page, "end_page": page}

            try:
                res = requests.post(
                    f"{JSON_SERVICE_URL}/ocr/json", files=files, data=data, timeout=600
                )
                if res.status_code == 200:
                    page_results = res.json().get("results", [])
                    results.extend(page_results)
                    progress_text.success(f"OCR หน้า {page} สำเร็จ")
                else:
                    progress_text.error(f"หน้า {page} เกิดข้อผิดพลาด: {res.status_code}")
                    break
            except Exception as e:
                progress_text.error(f"หน้า {page} เกิดข้อผิดพลาด: {e}")
                break

        # ถ้ามีผลลัพธ์ จึงดึง CSV จาก CSV Service
        if results:
            with st.spinner("กำลังดึงข้อมูลตาราง CSV..."):
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                files_csv = {"file": ("document.pdf", pdf_bytes, "application/pdf")}
                data_csv = {"start_page": start_page, "end_page": end_page}

                csv_res = requests.post(
                    f"{CSV_SERVICE_URL}/ocr/csv",
                    files=files_csv,
                    data=data_csv,
                    timeout=600,
                    stream=True
                )
                if csv_res.status_code == 200:
                    try:
                        buf = BytesIO()
                        for chunk in csv_res.iter_content(chunk_size=8192):
                            if chunk:
                                buf.write(chunk)
                        buf.seek(0)
                        df = pd.read_csv(buf)
                        # Drop unwanted column
                        if 'additional_information' in df.columns:
                            df = df.drop(columns=['additional_information'])
                        st.subheader("ข้อมูลแบบตาราง")
                        st.dataframe(df)

                        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
                        st.download_button(
                            "ดาวน์โหลด CSV", 
                            data=csv_data, 
                            file_name="ocr_result.csv", 
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถอ่านข้อมูล CSV: {e}")
                else:
                    st.warning(f"⚠️ ไม่สามารถโหลดข้อมูลตาราง: {csv_res.status_code} - {csv_res.text}")

            # แสดง JSON รายหน้า
            st.subheader("JSON รายหน้า")
            for r in results:
                if isinstance(r, dict) and 'additional_information' in r:
                    r.pop('additional_information', None)
                page = r.get("Page", "-")
                with st.expander(f"หน้า {page}"):
                    st.json(r)
        else:
            progress_text.warning("ไม่พบผลลัพธ์ OCR ใดๆ")
