#!/bin/bash
set -e

# Docker entrypoint for Litigant Portal
# Commands: web-dev, web-prod, migrate, collectstatic, shell, test

run_migrations() {
    echo "Running migrations..."
    python app/manage.py migrate --noinput
}

run_collectstatic() {
    echo "Collecting static files..."
    python app/manage.py collectstatic --noinput --clear
}

run_compilemessages() {
    echo "Compiling translation messages..."
    python app/manage.py compilemessages
}

case "$1" in
    web-dev)
        echo "Starting development server..."
        run_migrations
        sleep infinity | ./tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --watch &

        python app/manage.py runserver 0.0.0.0:8000
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
        exec python app/manage.py shell
        ;;

    test)
        ./tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify
        run_collectstatic
        exec python app/manage.py test "${@:2}"
        ;;

    *)
        exec "$@"
        ;;
esac
