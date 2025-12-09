.PHONY: help dev build clean install migrate test format lint

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python and npm dependencies
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/uv pip install -e .
	npm install

dev: ## Start Django + Tailwind CSS watch
	./dev.sh

django: ## Start Django dev server only
	source .venv/bin/activate && python manage.py runserver

css: ## Start Tailwind CSS watch only
	npm run watch:css

build: ## Build production CSS
	npm run build:css

migrate: ## Run Django migrations
	source .venv/bin/activate && python manage.py migrate

test: ## Run tests
	source .venv/bin/activate && python manage.py test

clean: ## Clean build artifacts
	rm -f static/css/main.built.css

superuser: ## Create Django superuser
	source .venv/bin/activate && python manage.py createsuperuser

shell: ## Open Django shell
	source .venv/bin/activate && python manage.py shell

format: ## Format all code (Python, JS, CSS, HTML templates)
	source .venv/bin/activate && ruff format .
	source .venv/bin/activate && djlint templates/ --reformat
	npm run format

lint: ## Lint all code (Python, HTML templates)
	source .venv/bin/activate && ruff check .
	source .venv/bin/activate && djlint templates/ --lint
	npm run format:check
