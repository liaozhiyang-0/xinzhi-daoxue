FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/apps/api

COPY apps/api/pyproject.toml /workspace/apps/api/pyproject.toml
COPY apps/api/app /workspace/apps/api/app
COPY apps/api/alembic /workspace/apps/api/alembic
COPY apps/api/alembic.ini /workspace/apps/api/alembic.ini
COPY agent_configs /workspace/agent_configs
COPY knowledge_config /workspace/knowledge_config
COPY evaluation/knowledge_retrieval /workspace/evaluation/knowledge_retrieval

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
