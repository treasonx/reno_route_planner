# syntax=docker/dockerfile:1
# Pass Check: single-process FastAPI service + built Preact frontend.
# Base images are pinned by digest (Dependabot keeps them fresh).

# --- 1. Frontend: built once on the build platform (assets are architecture-independent)
FROM --platform=$BUILDPLATFORM node:26-slim@sha256:e6bedef217677b276c591795e169840edd9096dbf13f29df8ef8d1856b8820bc AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Python dependencies into a venv with uv
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-editable

# --- 3. Runtime: same base + /app path as the builder so the venv works as-is
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
LABEL org.opencontainers.image.title="Pass Check" \
      org.opencontainers.image.description="GO / CAUTION / NO GO for crossing the Sierra between Reno and Sacramento" \
      org.opencontainers.image.source="https://github.com/treasonx/reno_route_planner"
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid 10001 --no-create-home app \
    && mkdir /data && chown 10001:10001 /data
WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --from=web --chown=10001:10001 /web/dist /app/static
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/static \
    DATA_DIR=/data
USER 10001:10001
# Last-good upstream responses for fast, safe restarts (mount a volume here to keep them).
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]
# Single worker on purpose: the data store and refresh scheduler live in-process.
CMD ["uvicorn", "passcheck.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--no-server-header", "--limit-concurrency", "100", "--timeout-keep-alive", "5"]
