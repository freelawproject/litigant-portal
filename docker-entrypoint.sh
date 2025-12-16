#!/bin/bash
set -e

# Docker entrypoint for Litigant Portal
# Commands: web-dev, web-prod, migrate, collectstatic, shell, test

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
        tailwindcss -i static/css/main.css -o static/css/main.built.css --watch &

        wait_for_db
        run_migrations

        exec python manage.py runserver 0.0.0.0:8000
        ;;

    web-prod)
        echo "Starting production server..."
        wait_for_db
        run_migrations
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
        tailwindcss -i static/css/main.css -o static/css/main.built.css --minify
        run_collectstatic
        exec python manage.py test "${@:2}"
        ;;

    *)
        exec "$@"
        ;;
esac
