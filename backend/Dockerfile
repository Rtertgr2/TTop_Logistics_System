FROM python:3.11-slim

WORKDIR /app

# ติดตั้ง system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# คัดลอก requirements
COPY requirements.txt .

# ติดตั้ง Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอก source code
COPY . .

# สร้าง directory สำหรับ data
RUN mkdir -p /app/data

# สร้าง non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# เริ่ม FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
