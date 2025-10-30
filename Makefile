.PHONY: help install dev build test test-py test-js lint format clean migrate run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (Python + Node.js)
	uv sync --extra dev
	npm install

dev: ## Run development servers (Django + Vite) in parallel
	@echo "Starting Vite dev server and Django..."
	@echo "Vite: http://localhost:5173"
	@echo "Django: http://localhost:8000"
	@trap 'kill 0' EXIT; \
		npm run dev & \
		source .venv/bin/activate && python manage.py runserver

build: ## Build production assets with Vite
	npm run build
	source .venv/bin/activate && python manage.py collectstatic --noinput

test: ## Run all tests (Python + JavaScript)
	@$(MAKE) test-py
	@$(MAKE) test-js

test-py: ## Run Python tests with pytest
	source .venv/bin/activate && pytest

test-js: ## Run JavaScript/TypeScript tests with Vitest
	npm test

test-js-ui: ## Run JavaScript tests with UI
	npm run test:ui

lint: ## Run all linters (Python + TypeScript + Templates)
	@echo "Linting Python..."
	source .venv/bin/activate && ruff check .
	source .venv/bin/activate && mypy portal config
	@echo "Linting TypeScript..."
	npm run lint
	@echo "Linting Templates..."
	source .venv/bin/activate && djlint templates/ --lint

format: ## Format all code (Python + TypeScript + Templates)
	@echo "Formatting Python..."
	source .venv/bin/activate && ruff format .
	@echo "Formatting TypeScript..."
	npm run format
	@echo "Formatting Templates..."
	source .venv/bin/activate && djlint templates/ --reformat

format-check: ## Check code formatting without making changes
	@echo "Checking Python formatting..."
	source .venv/bin/activate && ruff format --check .
	@echo "Checking TypeScript formatting..."
	npm run format:check
	@echo "Checking Template formatting..."
	source .venv/bin/activate && djlint templates/ --check

type-check: ## Run TypeScript type checking
	npm run type-check

migrate: ## Run Django migrations
	source .venv/bin/activate && python manage.py migrate

makemigrations: ## Create Django migrations
	source .venv/bin/activate && python manage.py makemigrations

run: ## Run Django development server only
	source .venv/bin/activate && python manage.py runserver

clean: ## Clean build artifacts and caches
	rm -rf staticfiles/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf node_modules/.vite/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
