# Mango OCR Invoice

ระบบ OCR สำหรับประมวลผลใบแจ้งหนี้ (Invoice) และให้บริการผ่าน API และ Web Interface


## คุณสมบัติ
- **JSON Service**: ให้บริการ OCR และส่งคืนข้อมูลในรูปแบบ JSON
- **CSV Service**: ให้บริการ OCR และส่งคืนข้อมูลในรูปแบบ CSV
- **Streamlit App**: หน้าเว็บสำหรับทดสอบและใช้งาน OCR แบบ Interactive


## วิธีรันแต่ละไฟล์ 
- **JSON Service**: uvicorn json_service:app --port 8000
- **CSV Service**: uvicorn csv_service:app --port 8001
- **Streamlit App**: streamlit run test_app.py
