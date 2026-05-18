#!/bin/bash
set -e

# Docker entrypoint for Litigant Portal
# Commands: web-dev, web-prod, migrate, collectstatic, shell, test

run_migrations() {
    echo "Running migrations..."
    manage migrate --noinput
}

run_collectstatic() {
    echo "Collecting static files..."
    manage collectstatic --noinput --clear
}

run_compilemessages() {
    echo "Compiling translation messages..."
    manage compilemessages
}

case "$1" in
    web-dev)
        echo "Starting development server at http://localhost ..."
        # Start Tailwind watch in background
        tailwindcss -i src/css/main.css -o static/css/main.built.css --watch &

        run_migrations

        exec manage runserver 0.0.0.0:8000
        ;;

    web-prod)
        echo "Starting production server..."
        run_compilemessages
        run_collectstatic
        run_migrations

        exec gunicorn litigant_portal.main:application \
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
        exec manage shell
        ;;

    test)
        tailwindcss -i src/css/main.css -o static/css/main.built.css --minify
        run_collectstatic
        exec tox "${@:2}"
        ;;

    *)
        exec "$@"
        ;;
esac
