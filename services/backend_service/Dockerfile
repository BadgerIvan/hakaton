FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/backend_service/requirements.txt .
COPY services/common /opt/partner-observability
RUN pip install --no-cache-dir /opt/partner-observability -r requirements.txt && useradd --create-home --uid 10001 appuser
COPY services/backend_service/app ./app
COPY services/backend_service/alembic.ini ./
COPY services/backend_service/migrations ./migrations
COPY services/backend_service/entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--workers", "1"]
