# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/apps/api

COPY apps/api/pyproject.toml /workspace/apps/api/pyproject.toml

# Keep the dependency layer independent from application source changes.  The
# project metadata remains the single source of truth for runtime dependencies.
RUN python - <<'PY'
import tomllib
from pathlib import Path

metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
dependencies = metadata["project"]["dependencies"]
Path("/tmp/runtime-requirements.txt").write_text(
    "\n".join(dependencies) + "\n",
    encoding="utf-8",
)
PY

# The Compose services run without a GPU by default.  Install the CPU wheel
# before resolving the remaining requirements so PyPI does not pull the full
# CUDA runtime into the API/Worker image.  Override this build argument for a
# deliberately GPU-enabled image.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_REQUIREMENT="torch>=2.7,<3"
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --no-deps \
      --index-url "${TORCH_INDEX_URL}" "${TORCH_REQUIREMENT}"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --requirement /tmp/runtime-requirements.txt

COPY apps/api/app /workspace/apps/api/app
COPY apps/api/alembic /workspace/apps/api/alembic
COPY apps/api/alembic.ini /workspace/apps/api/alembic.ini
COPY agent_configs /workspace/agent_configs
COPY config /workspace/config
COPY knowledge_config /workspace/knowledge_config
COPY evaluation/knowledge_retrieval /workspace/evaluation/knowledge_retrieval
COPY apps/worker /workspace/apps/worker

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --no-deps .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
