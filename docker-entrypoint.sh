#!/bin/bash
set -e

# Docker entrypoint for Litigant Portal
# Commands: web-dev, web-prod, migrate, collectstatic, shell, test

# ---------------------------------------------------------------------------
# Handle secrets from files (_FILE pattern for Docker secrets)
# ---------------------------------------------------------------------------

# SECRET_KEY: auto-generate for dev, or read from file for prod
if [ "$SECRET_KEY" = "auto" ]; then
    export SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
elif [ -n "$SECRET_KEY_FILE" ] && [ -f "$SECRET_KEY_FILE" ]; then
    export SECRET_KEY=$(cat "$SECRET_KEY_FILE")
fi

# Build DATABASE_URL from individual vars + secret file (for prod)
if [ -z "$DATABASE_URL" ] && [ -n "$POSTGRES_HOST" ]; then
    POSTGRES_PASSWORD_VALUE="$POSTGRES_PASSWORD"
    if [ -n "$POSTGRES_PASSWORD_FILE" ] && [ -f "$POSTGRES_PASSWORD_FILE" ]; then
        POSTGRES_PASSWORD_VALUE=$(cat "$POSTGRES_PASSWORD_FILE")
    fi
    export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD_VALUE}@${POSTGRES_HOST}:5432/${POSTGRES_DB}"
fi

wait_for_db() {
    if [ -z "$DATABASE_URL" ]; then
        return 0
    fi
    echo "Waiting for database..."
    python << 'EOF'
import os
import sys
import time
from urllib.parse import urlparse

url = urlparse(os.environ.get("DATABASE_URL", ""))
if url.scheme.startswith("postgres"):
    import psycopg
    for i in range(30):
        try:
            conn = psycopg.connect(
                host=url.hostname,
                port=url.port or 5432,
                user=url.username,
                password=url.password,
                dbname=url.path[1:],
            )
            conn.close()
            print("Database is ready!")
            sys.exit(0)
        except psycopg.OperationalError:
            print(f"Database not ready, waiting... ({i+1}/30)")
            time.sleep(2)
    print("Database connection timeout")
    sys.exit(1)
EOF
}

run_migrations() {
    echo "Running migrations..."
    python manage.py migrate --noinput
}

run_collectstatic() {
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear
}

case "$1" in
    web-dev)
        echo "Starting development server..."
        # Start Tailwind watch in background
        tailwindcss -i src/css/main.css -o static/css/main.built.css --watch &

        wait_for_db
        run_migrations

        exec python manage.py runserver 0.0.0.0:8000
        ;;

    web-prod)
        echo "Starting production server..."
        wait_for_db
        # Migrations handled by fly.toml release_command (or run separately)
        run_collectstatic

        exec gunicorn config.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers "${GUNICORN_WORKERS:-3}" \
            --threads "${GUNICORN_THREADS:-2}" \
            --timeout "${GUNICORN_TIMEOUT:-30}" \
            --access-logfile - \
            --error-logfile - \
            --capture-output
        ;;

    migrate)
        wait_for_db
        run_migrations
        ;;

    collectstatic)
        run_collectstatic
        ;;

    shell)
        exec python manage.py shell
        ;;

    test)
        tailwindcss -i src/css/main.css -o static/css/main.built.css --minify
        run_collectstatic
        exec python manage.py test "${@:2}"
        ;;

    *)
        exec "$@"
        ;;
esac
