# Single entry point for project commands (AGENTS.md §7).
# Works with GNU Make 3.81 (macOS default): no 4.x-only features are used.
# Toolchains per part: Go 1.23+ (agent/), Python 3.12+ (backend/), Node.js 24 (web/),
# Docker Compose (db, redis, speedtest).

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Local environment lives in .env (cp .env.example .env). Make reads it only for the
# POSTGRES_* variables of `make db-reset`; nothing is exported to recipes: the backend reads
# .env itself (pydantic-settings) and docker compose reads it for ${...} interpolation, so a
# value with `#` or `$` cannot be mangled by make on its way to the application.
-include .env

# Overridable parameters: make simulate n=500 days=30, make backend-install PYTHON=/path/to/python3.12
PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3 2>/dev/null || echo python3)
n ?= 1000
days ?= 90

.PHONY: help up down api worker web agent-run \
	check check-agent check-backend check-web \
	migrate migration db-reset seed simulate openapi \
	install agent-install backend-install web-install

help: ## Показать этот список команд
	@echo "Мониторинг интернета ВКО — команды разработчика (make <цель>):"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk 'BEGIN {FS = ":.*## "} {printf "  %-16s %s\n", $$1, $$2}'
	@echo
	@echo "Порты: api 8000, web 5173, db 5432, redis 6379, speedtest 8080, caddy 80/443."
	@echo "Перед первым запуском: cp .env.example .env && make install && make up"

# --- Infrastructure -----------------------------------------------------------------------

up: ## Поднять инфраструктуру для разработки: db, redis, speedtest (docker compose up -d)
	@test -f .env || { echo "Нет файла .env — выполните: cp .env.example .env" >&2; exit 1; }
	docker compose up -d db redis speedtest

down: ## Остановить контейнеры (docker compose down, без -v: данные остаются)
	docker compose down

# --- Run locally --------------------------------------------------------------------------

api: ## FastAPI с автоперезагрузкой на http://localhost:8000 (Swagger: /api/docs)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

worker: ## Celery worker + beat
	cd backend && .venv/bin/celery -A app.workers.celery_app worker -B --loglevel=info

web: ## Vite dev server панели на http://localhost:5173
	cd web && npm run dev

agent-run: ## Агент без установки службы: go run ./cmd/vko-agent run --config ./dev.yaml
	cd agent && go run ./cmd/vko-agent run --config ./dev.yaml

# --- Checks (run `make check` before every merge) -----------------------------------------

check: check-agent check-backend check-web ## ВСЁ: check-agent + check-backend + check-web

check-agent: ## Агент: gofmt -l, go vet, golangci-lint (если установлен), go test, go build
	cd agent && test -z "$$(gofmt -l . | tee /dev/stderr)"
	cd agent && go vet ./...
	@cd agent && if command -v golangci-lint >/dev/null 2>&1; then \
		echo "golangci-lint run ./..."; golangci-lint run ./...; \
	else \
		echo "предупреждение: golangci-lint не установлен — шаг пропущен (в CI он ставится автоматически)" >&2; \
	fi
	cd agent && go test ./...
	cd agent && go build ./...

check-backend: ## Backend: ruff check, ruff format --check, mypy app, pytest
	cd backend && .venv/bin/ruff check .
	cd backend && .venv/bin/ruff format --check .
	cd backend && .venv/bin/mypy app
	cd backend && .venv/bin/pytest

check-web: ## Панель: свежесть src/api/generated, eslint, tsc --noEmit, vitest run, vite build
	cd web && npm run api:check
	cd web && npm run lint
	cd web && npm run typecheck
	cd web && npm run test
	cd web && npm run build

# --- Database -----------------------------------------------------------------------------

migrate: ## Применить миграции: alembic upgrade head
	cd backend && .venv/bin/alembic upgrade head

migration: ## Новая миграция: make migration name=short_name (alembic revision --autogenerate)
	@test -n "$(name)" || { echo "Укажите имя миграции: make migration name=short_name" >&2; exit 1; }
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(name)"

db-reset: ## Пересоздать локальную БД: drop + create + migrate + seed (только локально)
	@[ -n "$(POSTGRES_USER)" ] && [ -n "$(POSTGRES_DB)" ] || { echo "Нет POSTGRES_USER / POSTGRES_DB — нужен .env (cp .env.example .env)" >&2; exit 1; }
	docker compose exec -T db psql -U "$(POSTGRES_USER)" -d postgres -c "DROP DATABASE IF EXISTS $(POSTGRES_DB) WITH (FORCE)" -c "CREATE DATABASE $(POSTGRES_DB)"
	$(MAKE) migrate
	$(MAKE) seed

seed: ## Справочники, GeoJSON районов ВКО, тестовые школы, dev-пользователи
	cd backend && .venv/bin/python -m app.seed

simulate: ## Симулятор агентов: make simulate n=1000 days=90
	cd backend && .venv/bin/python ../simulator/simulate.py --devices $(n) --days $(days)

openapi: ## Экспорт схемы в docs/reference/openapi.json + генерация web/src/api/generated
	cd backend && .venv/bin/python -m app.openapi_export ../docs/reference/openapi.json
	cd web && npm run api:generate

# --- Dependencies -------------------------------------------------------------------------

install: agent-install backend-install web-install ## Установить зависимости всех трёх частей

agent-install: ## Агент: go mod download
	cd agent && go mod download

backend-install: ## Backend: venv в backend/.venv и pip install -e ".[dev]"
	test -x backend/.venv/bin/python || $(PYTHON) -m venv backend/.venv
	cd backend && .venv/bin/pip install -e ".[dev]"

web-install: ## Панель: npm ci по package-lock.json (без lock-файла — npm install)
	cd web && if [ -f package-lock.json ]; then npm ci; else npm install; fi
