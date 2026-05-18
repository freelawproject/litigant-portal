#!/bin/bash
set -e

# Docker entrypoint for Litigant Portal
# Commands: web-dev, web-prod, test

run_migrations() {
    echo "Running migrations ..."
    manage migrate --noinput
}

run_collectstatic() {
    echo "Collecting static files ..."
    manage collectstatic --noinput --clear
}

run_compilemessages() {
    echo "Compiling translation messages ..."
    manage compilemessages
}

run_dev_server() {
    echo "Starting Tailwind watcher and development server..."
    /tmp/tailwindcss \
        -i /app/litigant_portal/app/static/css/main.css \
        -o /app/litigant_portal/app/static/css/main.built.css \
        --watch=always & manage runserver 0.0.0.0:8000
}

run_prod_server() {
    echo "Starting production server ..."
    gunicorn litigant_portal.main:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --threads "${GUNICORN_THREADS:-2}" \
        --timeout "${GUNICORN_TIMEOUT:-30}" \
        --access-logfile - \
        --error-logfile - \
        --capture-output
}

case "$1" in
    web-dev)
        echo "Starting development server ..."
        run_compilemessages
        run_collectstatic
        run_migrations
        run_dev_server
        ;;

    web-prod)
        echo "Starting production server ..."
        run_compilemessages
        run_collectstatic
        run_migrations
        run_prod_server
        ;;

    test)
        /tmp/tailwindcss \
            -i /app/litigant_portal/app/static/css/main.css \
            -o /app/litigant_portal/app/static/css/main.built.css \
            --minify
        run_collectstatic
        exec tox "${@:2}"
        ;;

    *)
        exec "$@"
        ;;
esac
