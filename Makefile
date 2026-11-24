VENV   := .venv
BIN    := $(VENV)/bin
PYTHON := $(BIN)/python

# put the venv first on PATH, so tools that start `python` get the venv's one
export PATH := $(abspath $(BIN)):$(PATH)
export VIRTUAL_ENV := $(abspath $(VENV))

.DEFAULT_GOAL := help
.PHONY: help venv install run dev console lint fix format check test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

$(PYTHON):
	python3 -m venv $(VENV)

venv: $(PYTHON) ## Create the virtualenv

install: $(PYTHON) ## Install the app and dev tools (editable)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

run: ## Run the app
	$(BIN)/grid-tui

dev: ## Run with live CSS reload (use `make console` in another terminal)
	$(BIN)/textual run --dev grid_tui.app:Grid5KApp

console: ## Open the Textual dev console for logs
	$(BIN)/textual console

lint: ## Check PEP 8 / code issues
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

fix: ## Auto-fix lint issues and format
	$(BIN)/ruff check . --fix
	$(BIN)/ruff format .

format: ## Format code
	$(BIN)/ruff format .

test: ## Run the tests
	$(BIN)/pytest

check: lint test ## Lint and test (before committing)

clean: ## Remove caches and build files
	rm -rf .pytest_cache .ruff_cache build dist src/*.egg-info
	find . -name __pycache__ -type d -not -path './$(VENV)/*' -exec rm -rf {} +
