.PHONY: help dev build css clean install migrate test collectstatic format lint

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo ""
	@echo "NOTE: Tailwind CSS CLI required (brew install tailwindcss)"

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

format: ## Format all code (Python + HTML templates)
	source .venv/bin/activate && ruff format .
	source .venv/bin/activate && djlint templates/ --reformat

lint: ## Lint all code (Python + HTML templates)
	source .venv/bin/activate && ruff check .
	source .venv/bin/activate && djlint templates/ --lint
