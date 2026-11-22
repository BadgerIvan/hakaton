FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/rag_service/requirements.txt .
COPY services/common /opt/partner-observability
RUN pip install --no-cache-dir /opt/partner-observability -r requirements.txt

COPY services/rag_service/app ./app
COPY services/rag_service/reindex.py ./reindex.py
RUN mkdir -p /app/data /app/logs && chown 10001:10001 /app/logs

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
