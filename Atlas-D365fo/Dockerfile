# D365 ATLAS backend — FastAPI. Single Uvicorn worker (t2.micro friendly).
FROM python:3.11-slim

WORKDIR /app

# Install backend deps first for layer caching.
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx

COPY backend/app ./app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/health').status_code==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
