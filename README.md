# ระบบจัดคิวรถและเส้นทางจัดส่งอัตโนมัติ

## เริ่มต้นใช้งาน

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints
- `POST /upload` - อัปโหลดไฟล์ PDF
- `POST /plan-routes` - คำนวณเส้นทาง

## TEST URL
- https://adventures-proceeds-modular-hello.trycloudflare.com
