FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/pyproject.toml /app/backend/
COPY backend/app /app/backend/app
RUN pip install /app/backend && useradd --create-home --uid 10001 appuser
COPY backend/alembic.ini /app/backend/
COPY backend/migrations /app/backend/migrations
COPY backend/scripts /app/backend/scripts
COPY database/seeds /app/database/seeds
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

FROM base AS api
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS worker
USER root
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.6,<3" && pip install '/app/backend[nlp]'
ENV HF_HOME=/models/huggingface STANZA_DIR=/models/stanza HF_HUB_DISABLE_XET=1
RUN mkdir -p /models && touch /models/.initialized && chown -R appuser:appuser /models
USER appuser
CMD ["python", "-m", "app.worker"]
