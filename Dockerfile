FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl gettext && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md ./
RUN mkdir app && touch app/__init__.py
RUN pip install --no-cache-dir .

# Install Tailwind CSS
COPY scripts scripts/
RUN ./scripts/install-tailwindcss.sh

# Add app code
COPY app/ app/

# Build CSS for prod
RUN ./tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify

# Install the package
RUN pip install --no-cache-dir .

# Create user and set permissions
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /data && chown appuser:appuser /data
USER appuser

ENV PYTHONPATH="/app/app:${PYTHONPATH}"

EXPOSE 8000

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["web-prod"]
