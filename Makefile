.DEFAULT_GOAL := help
SHELL := /bin/bash

PY      := .venv/bin/python
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy
PYTEST  := .venv/bin/pytest

GATEWAY ?= http://localhost:8080
SERVICES := auth tenants projects issues notifications audit

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------- Docker stack ----------

.PHONY: up
up: ## Start the full stack in the background
	docker compose up -d

.PHONY: down
down: ## Stop the stack (keeps DB volume)
	docker compose down

.PHONY: nuke
nuke: ## Stop the stack AND wipe the DB volume
	docker compose down -v

.PHONY: restart
restart: ## Recreate every container with the current images
	docker compose up -d --force-recreate

.PHONY: rebuild
rebuild: ## Rebuild all images and recreate containers
	docker compose up -d --build --force-recreate

.PHONY: ps
ps: ## Show container status
	docker compose ps

.PHONY: logs
logs: ## Tail logs from every service (Ctrl-C to stop)
	docker compose logs -f

.PHONY: logs-%
logs-%: ## Tail one service's logs (e.g. make logs-auth)
	docker compose logs -f $*

.PHONY: shell-db
shell-db: ## Open a psql shell on the running db container
	docker compose exec db psql -U $$(grep ^POSTGRES_USER .env | cut -d= -f2)

# ---------- Alembic migrations (per service) ----------

.PHONY: migrate-%
migrate-%: ## Apply migrations to one service (e.g. make migrate-auth)
	docker compose exec $* alembic upgrade head

.PHONY: revision-%
revision-%: ## Autogen a revision for one service (e.g. make revision-auth m="add comments")
	@if [ -z "$(m)" ]; then echo 'ERROR: pass a message, e.g. make revision-auth m="add comments"'; exit 1; fi
	docker compose exec $* alembic revision --autogenerate -m "$(m)"
	@echo
	@echo 'Generated file is owned by root inside the container; chown it on the host:'
	@echo '  sudo chown -R $$USER services/$*/alembic/versions'

.PHONY: migration-history-%
migration-history-%: ## Show migration history for one service (e.g. make migration-history-auth)
	docker compose exec $* alembic history --verbose

# ---------- Local dev environment (uv / .venv) ----------

.PHONY: sync
sync: ## Create/update .venv via uv from pyproject.toml + uv.lock
	uv sync

.PHONY: lint
lint: ## Lint with ruff
	$(RUFF) check .

.PHONY: fmt
fmt: ## Format with ruff
	$(RUFF) format .

.PHONY: typecheck
typecheck: ## Type-check services + shared with mypy
	$(MYPY) services shared

.PHONY: test
test: ## Run pytest (no tests yet)
	$(PYTEST)

.PHONY: check
check: lint typecheck test ## Run lint + typecheck + test

# ---------- Smoke test through the gateway ----------

.PHONY: smoke
smoke: ## Hit every service's /health through the gateway
	@for s in $(SERVICES); do \
	    code=$$(curl -s -o /dev/null -w '%{http_code}' $(GATEWAY)/$$s/health); \
	    printf "  %-9s %s\n" "$$s" "$$code"; \
	done
	@code=$$(curl -s -o /dev/null -w '%{http_code}' $(GATEWAY)/health); \
	    printf "  %-9s %s\n" "gateway" "$$code"

# ---------- Cleanup ----------

.PHONY: clean
clean: ## Remove caches (.pytest_cache, .mypy_cache, .ruff_cache, __pycache__)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
