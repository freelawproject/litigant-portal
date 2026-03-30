# Litigant Portal Dockerfile
# Single image for both dev and prod. Dev uses volume mounts + command override.

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
# Stage 2: Dependencies - install production Python packages
# -----------------------------------------------------------------------------
FROM base AS dependencies

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# -----------------------------------------------------------------------------
# Stage 3: Tailwind - build production CSS
# -----------------------------------------------------------------------------
FROM base AS tailwind

ARG TAILWIND_VERSION=v4.1.16
COPY scripts/install-tailwind.sh /tmp/install-tailwind.sh
RUN TAILWIND_VERSION=${TAILWIND_VERSION} TAILWIND_DEST=/usr/local/bin/tailwindcss \
    bash /tmp/install-tailwind.sh

COPY src/css/main.css ./src/css/main.css
COPY templates/ ./templates/

RUN tailwindcss -i src/css/main.css -o static/css/main.built.css --minify

# -----------------------------------------------------------------------------
# Stage 4: Final application image
# -----------------------------------------------------------------------------
FROM base

# Python dependencies at /opt/venv so dev volume mounts (.:/app) don't shadow them
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Pre-built CSS from tailwind stage
COPY --from=tailwind /app/static/css/main.built.css ./static/css/main.built.css

# Tailwind binary (needed at runtime for dev watch mode)
COPY --from=tailwind /usr/local/bin/tailwindcss /usr/local/bin/tailwindcss

# Application code
COPY config/ ./config/
COPY portal/ ./portal/
COPY chat/ ./chat/
COPY litigant_portal/ ./litigant_portal/
COPY templates/ ./templates/
COPY static/ ./static/
COPY locale/ ./locale/
COPY manage.py ./

# Entrypoint
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["web-prod"]
