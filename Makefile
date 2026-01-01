.PHONY: help dev build css clean install migrate test collectstatic lint \
       docker-build docker-dev docker-prod docker-down docker-logs docker-shell docker-migrate docker-test docker-clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies (includes Tailwind CSS)
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

dev: ## Start Django + Tailwind CSS watch
	./dev.sh

django: ## Start Django dev server only
	source .venv/bin/activate && python manage.py runserver

css: ## Build Tailwind CSS (one-time)
	tailwindcss -i static/css/main.css -o static/css/main.built.css

css-watch: ## Watch Tailwind CSS for changes
	tailwindcss -i static/css/main.css -o static/css/main.built.css --watch

css-prod: ## Build production CSS (minified)
	tailwindcss -i static/css/main.css -o static/css/main.built.css --minify

migrate: ## Run Django migrations
	source .venv/bin/activate && python manage.py migrate

test: ## Run tests (builds CSS + collectstatic first)
	tailwindcss -i static/css/main.css -o static/css/main.built.css --minify
	source .venv/bin/activate && python manage.py collectstatic --noinput --clear
	source .venv/bin/activate && python manage.py test

collectstatic: ## Collect static files (builds CSS first)
	tailwindcss -i static/css/main.css -o static/css/main.built.css --minify
	source .venv/bin/activate && python manage.py collectstatic --noinput --clear

clean: ## Clean build artifacts
	rm -f static/css/main.built.css

superuser: ## Create Django superuser
	source .venv/bin/activate && python manage.py createsuperuser

shell: ## Open Django shell
	source .venv/bin/activate && python manage.py shell

lint: ## Lint and format all code (via pre-commit)
	pre-commit run --all-files

# Docker targets
docker-build: ## Build Docker images
	docker compose build

docker-dev: ## Start dev environment (Django + Tailwind watch + PostgreSQL)
	docker compose --profile dev up

docker-dev-build: ## Build and start dev environment
	docker compose --profile dev up --build

docker-prod: ## Start production environment (Gunicorn + PostgreSQL)
	docker compose --profile prod up

docker-prod-build: ## Build and start production environment
	docker compose --profile prod up --build

docker-down: ## Stop all containers
	docker compose --profile dev --profile prod down

docker-logs: ## View container logs
	docker compose --profile dev logs -f

docker-shell: ## Open shell in Django dev container
	docker compose --profile dev exec django-dev bash

docker-migrate: ## Run migrations in Docker
	docker compose --profile dev exec django-dev python manage.py migrate

docker-test: ## Run tests in Docker
	docker compose --profile dev exec django-dev python manage.py test

docker-clean: ## Remove containers, volumes, and images
	docker compose --profile dev --profile prod down -v --rmi local
