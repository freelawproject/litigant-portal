.PHONY: help install lint test test-v pre-commit \
	   css css-watch css-minify clean \
	   migrate shell collectstatic superuser messages compilemessages \
	   docker docker-build docker-up-build docker-down docker-logs docker-bash docker-clean \
	   docassemble-up docassemble-down \
	   file-issue build-image push-image

# Guard for commands that require the Docker container to be running
require-docker = docker compose exec -T django true 2>/dev/null || \
  { echo "Django container isn't running — start it with: make docker"; exit 1; }

# Tailwind source + built output (the path base.html resolves via {% static %})
CSS_SRC = litigant_portal/app/src/main.css
CSS_OUT = litigant_portal/app/static/css/main.built.css


help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies with dev extras
	uv sync --extra dev

lint: ## Run pre-commit hooks to lint and format code
	pre-commit run --all-files

test: ## Run tests
	$(require-docker)
	docker compose exec django docker/django/entrypoint.sh test -q -- -q --tb=short $(filter-out $@,$(MAKECMDGOALS))

test-v: ## Run tests — verbose output
	$(require-docker)
	docker compose exec django docker/django/entrypoint.sh test $(filter-out $@,$(MAKECMDGOALS))

pre-commit: ## Lint then test — stops if lint fails/fixes anything
	$(MAKE) lint && $(MAKE) test

css: ## Build Tailwind CSS (one-time)
	tailwindcss -i $(CSS_SRC) -o $(CSS_OUT)

css-watch: ## Watch Tailwind CSS for changes
	tailwindcss -i $(CSS_SRC) -o $(CSS_OUT) --watch

css-minify: ## Build minified CSS
	tailwindcss -i $(CSS_SRC) -o $(CSS_OUT) --minify

clean: ## Clean build artifacts
	rm -f $(CSS_OUT)
	rm -rf litigant_portal/app/staticfiles/


# Django management commands
migrate: ## Run database migrations
	$(require-docker)
	docker compose exec django manage migrate

shell: ## Open Django shell
	$(require-docker)
	docker compose exec django manage shell

collectstatic: ## Collect static files (builds CSS first)
	$(require-docker)
	$(MAKE) css-minify
	docker compose exec django manage collectstatic --noinput --clear

superuser: ## Create Django superuser
	$(require-docker)
	docker compose exec django manage createsuperuser

messages: ## Extract translation strings (all languages)
	$(require-docker)
	docker compose exec django manage makemessages -a --no-location
	docker compose exec django manage makemessages -d djangojs -a --no-location

compilemessages: ## Compile .po to .mo files
	$(require-docker)
	docker compose exec django manage compilemessages


# Docker targets
docker: ## Start local environment
	docker compose up

docker-build: ## Build Docker images
	docker compose build

docker-up-build: ## Build and start local environment
	docker compose up --build

docker-down: ## Stop all containers
	docker compose down

docker-logs: ## View container logs
	docker compose logs -f

docker-bash: ## Open a bash shell in the Django container
	docker compose exec django bash

docker-clean: ## Remove containers, volumes, and images
	docker compose down -v --rmi local

docassemble-up: ## Start the local-dev docassemble bench (http://localhost:8100)
	docker compose -f docker-compose.docassemble.yml up -d

docassemble-down: ## Stop the local-dev docassemble bench
	docker compose -f docker-compose.docassemble.yml down


file-issue: ## Build a prefilled GitHub issue-form URL from a content blob (stdin or FILE=path)
	uv run python scripts/file_issue.py $(FILE)

# Image build & push — used by .github/workflows/deploy.yml to publish the
# portal image for the EKS deploy. Requires VERSION (the short git SHA in CI):
#   make push-image -e VERSION=$(git rev-parse --short HEAD)
# Override the registry/namespace with -e REPO=... if needed.
REPO ?= freelawproject/litigant-portal
DOCKER_TAG_PROD = $(VERSION)-prod

build-image: ## Build the prod portal image (requires VERSION=...)
	docker build -t $(REPO):$(DOCKER_TAG_PROD) --file docker/django/Dockerfile .

push-image: build-image ## Build then push the prod portal image (amd64 only)
	@if [ "$$(uname -m)" != "x86_64" ]; then \
		echo "Refusing to push: only amd64 builds may be pushed (the server/EKS runs amd64; an arm64 image would crash-loop there)."; \
		exit 1; \
	fi
	docker push $(REPO):$(DOCKER_TAG_PROD)
