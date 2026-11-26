VENV   := .venv
BIN    := $(VENV)/bin
PYTHON := $(BIN)/python

# put the venv first on PATH, so tools that start `python` get the venv's one
export PATH := $(abspath $(BIN)):$(PATH)
export VIRTUAL_ENV := $(abspath $(VENV))

.DEFAULT_GOAL := help
.PHONY: help venv install run dev console secret lint fix format sort check test clean

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

SECRET_DIR := $(HOME)/.grid-secret

secret: ## Save your Grid'5000 login, base64-encoded, in ~/.grid-secret
	@mkdir -p $(SECRET_DIR) && chmod 700 $(SECRET_DIR)
	@printf "Grid'5000 user: "; read user; \
	 printf 'Password: '; stty -echo; read pass; stty echo; echo; \
	 printf '%s' "$$user" | base64 > $(SECRET_DIR)/G5K_USER; \
	 printf '%s' "$$pass" | base64 > $(SECRET_DIR)/G5K_PASSWORD; \
	 chmod 600 $(SECRET_DIR)/G5K_USER $(SECRET_DIR)/G5K_PASSWORD; \
	 echo "Saved in $(SECRET_DIR)"

lint: ## Check PEP 8 / code issues and import order
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/isort --check-only --diff src tests

fix: ## Auto-fix lint issues, sort imports and format
	$(BIN)/isort src tests
	$(BIN)/ruff check . --fix
	$(BIN)/ruff format .

sort: ## Sort imports
	$(BIN)/isort src tests

format: ## Format code
	$(BIN)/ruff format .

test: ## Run the tests
	$(BIN)/pytest

check: lint test ## Lint and test (before committing)

clean: ## Remove caches and build files
	rm -rf .pytest_cache .ruff_cache build dist src/*.egg-info
	find . -name __pycache__ -type d -not -path './$(VENV)/*' -exec rm -rf {} +
