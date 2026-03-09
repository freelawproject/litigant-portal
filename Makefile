.PHONY: help build css clean install migrate test collectstatic lint \
       messages compilemessages \
       docker-build docker-dev docker-prod docker-down docker-logs docker-shell docker-migrate docker-test docker-clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies (includes Tailwind CSS)
	uv sync --extra dev

css: ## Build Tailwind CSS (one-time)
	tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css

css-watch: ## Watch Tailwind CSS for changes
	tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --watch

css-prod: ## Build production CSS (minified)
	tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify

migrate: ## Run Django migrations
	uv run python app/manage.py migrate

test: ## Run tests (builds CSS + collectstatic first, uses tox)
	tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify
	uv run python app/manage.py collectstatic --noinput --clear
	tox

collectstatic: ## Collect static files (builds CSS first)
	tailwindcss -i app/src/css/main.css -o app/static/css/main.built.css --minify
	uv run python app/manage.py collectstatic --noinput --clear

clean: ## Clean build artifacts
	rm -f app/static/css/main.built.css

superuser: ## Create Django superuser
	uv run python app/manage.py createsuperuser

shell: ## Open Django shell
	uv run python app/manage.py shell

lint: ## Lint and format all code (via pre-commit)
	pre-commit run --all-files

messages: ## Extract translation strings (all languages)
	uv run python app/manage.py makemessages -a --no-location
	uv run python app/manage.py makemessages -d djangojs -a --no-location

compilemessages: ## Compile .po to .mo files
	uv run python app/manage.py compilemessages

# Docker targets
docker-build: ## Build Docker images
	docker compose build

docker-dev: ## Start dev environment (Django + Tailwind watch + SQLite)
	docker compose --profile dev up

docker-dev-build: ## Build and start dev environment
	docker compose --profile dev up --build

docker-prod: ## Start production environment (Gunicorn + SQLite)
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
