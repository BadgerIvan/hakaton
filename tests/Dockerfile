FROM python:3.12-slim
WORKDIR /project
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY services ./services
COPY parse_service ./parse_service
COPY requirements-test.txt pytest.ini ./
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
COPY scripts ./scripts
