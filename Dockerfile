# Litigant Portal Dockerfile
# Multi-stage build for development and production

# -----------------------------------------------------------------------------
# Stage 1: Base image with Python and system dependencies
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gettext \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# -----------------------------------------------------------------------------
# Stage 2: Dependencies - install Python packages
# -----------------------------------------------------------------------------
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# -----------------------------------------------------------------------------
# Stage 3: Tailwind - download standalone CLI
# -----------------------------------------------------------------------------
COPY app/src/css/main.css ./app/src/css/main.css
COPY app/templates/ ./app/templates/
COPY scripts scripts/

RUN ./scripts/install-tailwindcss.sh
RUN ./tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify


# -----------------------------------------------------------------------------
# Stage 4: Add code and build CSS
# -----------------------------------------------------------------------------
ENV PATH="/app/.venv/bin:$PATH"
COPY app/ app/
RUN ./tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /data && chown appuser:appuser /data
USER appuser

ENV PYTHONPATH="/app/app:${PYTHONPATH}"

EXPOSE 8000

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["web-prod"]
