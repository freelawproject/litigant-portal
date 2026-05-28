# Litigant Portal Dockerfile

# -----------------------------------------------------------------------------
# Stage 1: Base image with Python and system dependencies
# -----------------------------------------------------------------------------
FROM python:3.13-slim

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
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md LICENSE tox.ini .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --extra test --frozen --no-install-project --no-dev

# -----------------------------------------------------------------------------
# Stage 3: Install Tailwind CLI binary
# -----------------------------------------------------------------------------
COPY docker docker

ARG TAILWIND_VERSION=v4.1.16
RUN TAILWIND_VERSION=${TAILWIND_VERSION} \
    TAILWIND_DEST=/tmp/tailwindcss \
    bash docker/django/install-tailwind.sh

# -----------------------------------------------------------------------------
# Stage 4: Application code
# -----------------------------------------------------------------------------
COPY litigant_portal litigant_portal

RUN /tmp/tailwindcss \
    -i /app/litigant_portal/app/static/css/main.css \
    -o /app/litigant_portal/app/static/css/main.built.css \
    --minify

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps --python /opt/venv/bin/python -e .

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["docker/django/entrypoint.sh"]
CMD ["web-prod"]
