# ABOUTME: Production image for the Hangar Bay FastAPI backend — uvicorn with ONE worker,
# ABOUTME: because the APScheduler ingestion job runs in-process (spec §2: N workers = N schedulers).
FROM python:3.14-slim AS deps
WORKDIR /app
RUN pip install --no-cache-dir pdm
COPY pyproject.toml pdm.lock ./
RUN pdm export --prod -o requirements.txt --without-hashes

# The locked asyncpg/httptools/uvloop versions publish no CPython 3.14 wheels, so they
# compile from source — this stage carries the compiler; the runtime stage stays slim.
FROM python:3.14-slim AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY --from=deps /app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.14-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY src/ ./src/
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# --workers 1 is a design constraint, not a tuning choice (spec §2). Do not raise it.
CMD ["sh", "-c", "uvicorn fastapi_app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
