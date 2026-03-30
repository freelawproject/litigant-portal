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

run_migrations() {
    echo "Running migrations..."
    python manage.py migrate --noinput
}

run_collectstatic() {
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear
}

run_compilemessages() {
    echo "Compiling translation messages..."
    python manage.py compilemessages
}

case "$1" in
    web-dev)
        echo "Starting development server at http://localhost ..."
        # Start Tailwind watch in background
        tailwindcss -i src/css/main.css -o static/css/main.built.css --watch &

        run_migrations

        exec python manage.py runserver 0.0.0.0:8000
        ;;

    web-prod)
        echo "Starting production server..."
        run_compilemessages
        run_collectstatic
        run_migrations

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
