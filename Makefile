.DEFAULT_GOAL := help
.PHONY: help build install start stop up down logs test tests integration lint format check uv lock hooks-install pre-commit

DOCKER ?= docker
COMPOSE ?= $(DOCKER) compose
UV_IMAGE := ghcr.io/astral-sh/uv:0.13.1-python3.11-trixie-slim
ARGS ?= --help
PRE_COMMIT_ARGS ?= --all-files
RUN = $(COMPOSE) run --rm --no-deps -T api
FORMAT_RUN = $(COMPOSE) run --rm --no-deps -T \
	--user "$$(id -u):$$(id -g)" \
	-e UV_CACHE_DIR=/tmp/uv -e RUFF_CACHE_DIR=/tmp/ruff \
	-e UV_PROJECT_ENVIRONMENT=/app/.venv \
	-v "$(CURDIR):/workspace:rw" -w /workspace api
# Keep host paths so Git's alternate index (e.g. git commit -a) also works in Docker.
PRE_COMMIT_RUN = $(COMPOSE) run --rm --no-deps -T \
	--user "$$(id -u):$$(id -g)" \
	-e UV_CACHE_DIR=/tmp/uv -e RUFF_CACHE_DIR=/tmp/ruff \
	-e UV_PROJECT_ENVIRONMENT=/app/.venv -e PRE_COMMIT_HOME=/tmp/pre-commit \
	-e GIT_INDEX_FILE \
	-v "$(CURDIR):$(CURDIR):rw" -w "$(CURDIR)" api

help:
	@printf '%s\n' \
	  'make start       Start Docker services with API live reload and debug logs' \
	  'make stop        Stop services; preserve containers and data' \
	  'make tests       Run unit tests in Docker; databases not required' \
	  'make integration Start the stack and run integration tests in Docker' \
	  'make check       Run lint, formatting checks, and unit tests in Docker' \
	  'make format      Format source files using Docker' \
	  'make hooks-install Enable Docker pre-commit hooks in this clone' \
	  'make pre-commit  Run hooks on all tracked files in Docker' \
	  'make logs        Follow API logs' \
	  'make build       Build the image and install dependencies inside Docker' \
	  'make lock        Update uv.lock using Docker' \
	  'make uv ARGS=... Run a uv dependency command inside Docker'

build:
	$(COMPOSE) build api

install: build

start:
	$(COMPOSE) up --build -d --wait --wait-timeout 180

stop:
	$(COMPOSE) stop

up: start

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100 api

tests: test

test: build
	$(RUN) uv run --no-sync pytest -m "not integration" --cov=app

integration: start
	$(COMPOSE) exec -T -e RUN_INTEGRATION=1 api uv run --no-sync pytest -m integration

lint: build
	$(RUN) uv run --no-sync ruff check .
	$(RUN) uv run --no-sync ruff format --check .

format: build
	$(FORMAT_RUN) uv run --no-sync ruff format app tests
	$(FORMAT_RUN) uv run --no-sync ruff check --fix app tests

check: lint test

hooks-install:
	chmod +x .githooks/pre-commit
	git config --local core.hooksPath .githooks

pre-commit: build
	$(PRE_COMMIT_RUN) uv run --no-sync pre-commit run $(PRE_COMMIT_ARGS)

# A standalone uv image can update a stale lock before the application image builds.
uv:
	$(DOCKER) run --rm --user "$$(id -u):$$(id -g)" \
	  -e UV_CACHE_DIR=/tmp/uv -e UV_PROJECT_ENVIRONMENT=/tmp/venv \
	  -v "$(CURDIR):/workspace" -w /workspace --entrypoint uv $(UV_IMAGE) $(ARGS)

lock:
	$(MAKE) uv ARGS=lock
