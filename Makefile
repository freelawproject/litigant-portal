.PHONY: help dev build clean install migrate test

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python and npm dependencies
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/uv pip install -e .
	npm install

dev: ## Start Django + Vite dev servers (requires tmux or run in separate terminals)
	@echo "Starting development servers..."
	@echo "Django: http://localhost:8000"
	@echo "Vite: http://localhost:5173"
	@echo ""
	@if command -v tmux >/dev/null 2>&1; then \
		tmux new-session -d -s litigant-portal 'source .venv/bin/activate && python manage.py runserver'; \
		tmux split-window -v 'npm run dev'; \
		tmux attach -t litigant-portal; \
	else \
		echo "tmux not found. Run these commands in separate terminals:"; \
		echo "  Terminal 1: make django"; \
		echo "  Terminal 2: make vite"; \
	fi

django: ## Start Django dev server only
	source .venv/bin/activate && python manage.py runserver

vite: ## Start Vite dev server only
	npm run dev

build: ## Build production assets
	npm run build

migrate: ## Run Django migrations
	source .venv/bin/activate && python manage.py migrate

test: ## Run tests
	source .venv/bin/activate && python manage.py test
	npm run test

clean: ## Clean build artifacts
	rm -rf static/.vite
	rm -rf static/css
	rm -rf static/js
	rm -rf node_modules/.vite

superuser: ## Create Django superuser
	source .venv/bin/activate && python manage.py createsuperuser

shell: ## Open Django shell
	source .venv/bin/activate && python manage.py shell
