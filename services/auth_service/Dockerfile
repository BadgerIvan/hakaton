FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/auth_service/requirements.txt .
COPY services/common /opt/partner-observability
RUN pip install --no-cache-dir /opt/partner-observability -r requirements.txt && useradd --create-home --uid 10001 appuser
COPY services/auth_service/app ./app
COPY services/auth_service/alembic.ini ./
COPY services/auth_service/migrations ./migrations
COPY services/auth_service/entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh && mkdir -p /app/logs && chown -R appuser:appuser /app
USER appuser
EXPOSE 8002
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log", "--workers", "1"]
