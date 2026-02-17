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

enable_wal() {
    # Enable WAL mode for SQLite (better concurrency under Gunicorn)
    if echo "$DATABASE_URL" | grep -q "sqlite"; then
        python -c "
import dj_database_url, sqlite3, os
db = dj_database_url.config(default=os.environ.get('DATABASE_URL', ''))
path = db.get('NAME', '')
if path:
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.close()
    print(f'SQLite WAL mode enabled: {path}')
"
    fi
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

        run_migrations

        exec python manage.py runserver 0.0.0.0:8000
        ;;

    web-prod)
        echo "Starting production server..."
        enable_wal
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
