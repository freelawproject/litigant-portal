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
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# -----------------------------------------------------------------------------
# Stage 2: Dependencies - install Python packages (production only)
# -----------------------------------------------------------------------------
FROM base AS dependencies

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# -----------------------------------------------------------------------------
# Stage 3: Tailwind - download standalone CLI and build CSS
# -----------------------------------------------------------------------------
FROM base AS tailwind

ARG TARGETARCH
ARG TAILWIND_VERSION=v4.1.16
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "x64") \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${ARCH} \
    && chmod +x tailwindcss-linux-${ARCH} \
    && mv tailwindcss-linux-${ARCH} /usr/local/bin/tailwindcss

COPY static/css/main.css ./static/css/main.css
COPY templates/ ./templates/

RUN tailwindcss -i static/css/main.css -o static/css/main.built.css --minify

# -----------------------------------------------------------------------------
# Stage 4: Development image
# -----------------------------------------------------------------------------
FROM base AS development

# Install venv to /opt/venv to avoid conflict with host .venv mount
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

ARG TARGETARCH
ARG TAILWIND_VERSION=v4.1.16
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "x64") \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${ARCH} \
    && chmod +x tailwindcss-linux-${ARCH} \
    && mv tailwindcss-linux-${ARCH} /usr/local/bin/tailwindcss

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["web-dev"]

# -----------------------------------------------------------------------------
# Stage 5: Production image
# -----------------------------------------------------------------------------
FROM base AS production

COPY --from=dependencies /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=tailwind /app/static/css/main.built.css ./static/css/main.built.css

COPY config/ ./config/
COPY portal/ ./portal/
COPY chat/ ./chat/
COPY litigant_portal/ ./litigant_portal/
COPY chat/ ./chat/
COPY templates/ ./templates/
COPY static/ ./static/
COPY manage.py ./

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["web-prod"]
