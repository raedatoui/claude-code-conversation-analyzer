.PHONY: help install install-dev format lint type-check test clean build check-all setup-cclog update-cclog clean-cclog-output generate-cclog-data conversations-analysis all

# === CONFIGURATION === #

# claude-code-log configuration
CCLOG_REPO_UPSTREAM = git@github.com:daaain/claude-code-log.git
CCLOG_CONFIG = .cclog-config
CLAUDE_PROJECTS = $(HOME)/.claude/projects
CCLOG_DB = $(CLAUDE_PROJECTS)/claude-code-log-cache.db

# === HELP & SETUP === #

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-30s %s\n", $$1, $$2}'

install: ## Install the package (production dependencies only)
	uv sync --no-dev

install-dev: ## Install the package with development dependencies
	uv sync

# === CODE QUALITY === #

fmt: ## Format code with ruff
	uv run ruff format .

lint: ## Lint code with ruff
	uv run ruff check .

lint-fix: ## Lint and fix code with ruff
	uv run ruff check --fix .

type-check: ## Run type checking with mypy
	uv run mypy src/

check: lint type-check ## Run all checks (lint and type-check)

test: ## Run tests (placeholder - add test framework if needed)
	@echo "No tests configured yet"

# === BUILD & CLEAN === #

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

build: ## Build the package
	uv run python -m build

# === CLAUDE-CODE-LOG INTEGRATION === #

setup-cclog: ## Set up claude-code-log repository (prompts for location on first run)
	@if [ ! -f "$(CCLOG_CONFIG)" ]; then \
		echo "=== claude-code-log Setup ==="; \
		echo ""; \
		echo "Where would you like to clone claude-code-log?"; \
		echo "  1) $(HOME)/work/claude-code-log (recommended, next to collab/)"; \
		echo "  2) $(HOME)/.cache/claude-code-log (cache directory)"; \
		echo "  3) Custom path (you specify)"; \
		echo ""; \
		read -p "Choose [1-3]: " choice; \
		case $$choice in \
			1) CCLOG_PATH="$(HOME)/work/claude-code-log" ;; \
			2) CCLOG_PATH="$(HOME)/.cache/claude-code-log" ;; \
			3) read -p "Enter full path: " CCLOG_PATH ;; \
			*) echo "Invalid choice. Defaulting to $(HOME)/work/claude-code-log"; \
			   CCLOG_PATH="$(HOME)/work/claude-code-log" ;; \
		esac; \
		echo "$$CCLOG_PATH" > $(CCLOG_CONFIG); \
		echo "Configuration saved to $(CCLOG_CONFIG)"; \
		echo ""; \
	fi
	@CCLOG_DIR=$$(cat $(CCLOG_CONFIG)); \
	if [ ! -d "$$CCLOG_DIR" ]; then \
		echo "Cloning claude-code-log..."; \
		mkdir -p "$$(dirname "$$CCLOG_DIR")"; \
		git clone $(CCLOG_REPO_UPSTREAM) "$$CCLOG_DIR"; \
		echo "Installing dependencies with uv..."; \
		cd "$$CCLOG_DIR" && uv sync; \
		echo "claude-code-log setup complete at $$CCLOG_DIR"; \
	else \
		echo "claude-code-log already exists at $$CCLOG_DIR"; \
	fi

update-cclog: setup-cclog ## Pull latest changes from origin claude-code-log
	@CCLOG_DIR=$$(cat $(CCLOG_CONFIG)); \
	echo "Updating claude-code-log from origin..."; \
	cd "$$CCLOG_DIR" && git fetch origin; \
	cd "$$CCLOG_DIR" && git merge origin/main --no-edit; \
	cd "$$CCLOG_DIR" && uv sync; \
	echo "claude-code-log updated to latest origin"

clean-cclog-output: ## Delete old cclog output files from ~/.claude/projects
	@echo "Cleaning old claude-code-log output files..."
	@find $(CLAUDE_PROJECTS) -name "*.html" -type f -print -delete 2>/dev/null || true
	@find $(CLAUDE_PROJECTS) -name "full-transcripts.json" -type f -print -delete 2>/dev/null || true
	@rm -f $(CLAUDE_PROJECTS)/all-projects-summary.json 2>/dev/null || true
	@echo "Cleaned old output files"

generate-cclog-data: setup-cclog ## Generate full-transcripts.json files for all projects
	@CCLOG_DIR=$$(cat $(CCLOG_CONFIG)); \
	echo "Generating cclog data for all projects..."; \
	cd "$$CCLOG_DIR" && uv run python -m claude_code_log.cli --all-projects; \
	echo "Generated full-transcripts.json files in $(CLAUDE_PROJECTS)"

# === CONVERSATION RATING ANALYSIS === #

conversations-analysis: ## Run conversation analysis (reads cclog DB, augments with costs/quality)
	@echo "Running conversation analysis..."
	uv run python -m src.app \
		--cclog-db $(CCLOG_DB) \
		--claude-projects $(CLAUDE_PROJECTS) \
		--verbose

all: setup-cclog update-cclog clean-cclog-output generate-cclog-data conversations-analysis ## Run full pipeline: setup -> update -> clean -> generate -> analyze

check-all: install-dev fmt lint type-check ## Install dependencies, format, lint, and type-check
