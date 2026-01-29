# Include check.mk for lint and format checks
include check.mk

########################################################################################################################
# VARIABLES
########################################################################################################################

# Python interpreter
PYTHON = python
PYTEST = pytest
UV = uv

########################################################################################################################
# DEVELOPMENT ENVIRONMENT
########################################################################################################################

.PHONY: setup
setup: ## Install core dependencies
	@echo "Installing SyGra core dependencies"
	$(UV) sync

.PHONY: setup-all
setup-all: ## Install core and extra dependencies
	@echo "Installing SyGra Core and extra dependencies"
	$(UV) sync

.PHONY: setup-dev
setup-dev: ## Install development dependencies
	@echo "Installing SyGra Core, Extra and Development dependencies"
	$(UV) sync --extra dev

########################################################################################################################
# SYGRA STUDIO
########################################################################################################################

# Studio directories
STUDIO_DIR = studio
STUDIO_FRONTEND_DIR = $(STUDIO_DIR)/frontend
STUDIO_BUILD_DIR = $(STUDIO_FRONTEND_DIR)/build

# Studio configuration (can be overridden: make studio TASKS_DIR=./my/tasks PORT=9000)
TASKS_DIR ?= ./tasks/examples
PORT ?= 8000

.PHONY: studio
studio: studio-build ## Launch SyGra Studio (builds frontend if needed, starts server)
	@echo "🚀 Starting SyGra Studio..."
	@echo "   Tasks: $(TASKS_DIR)"
	@echo "   Port:  $(PORT)"
	$(UV) run $(PYTHON) -m studio.server --svelte --tasks-dir $(TASKS_DIR) --port $(PORT)

.PHONY: studio-build
studio-build: ## Build the Studio frontend (only if not already built)
	@if [ ! -d "$(STUDIO_BUILD_DIR)" ] || [ ! -f "$(STUDIO_BUILD_DIR)/index.html" ]; then \
		echo "📦 Building Studio frontend..."; \
		cd $(STUDIO_FRONTEND_DIR) && npm install && npm run build; \
	else \
		echo "✅ Studio frontend already built. Use 'make studio-rebuild' to force rebuild."; \
	fi

.PHONY: studio-rebuild
studio-rebuild: ## Force rebuild the Studio frontend
	@echo "🔨 Rebuilding Studio frontend..."
	cd $(STUDIO_FRONTEND_DIR) && npm install && npm run build

.PHONY: studio-dev
studio-dev: ## Launch Studio in development mode (hot-reload for frontend)
	@echo "🔧 Starting Studio in development mode..."
	@echo "   Backend: http://localhost:$(PORT)"
	@echo "   Frontend: http://localhost:5173 (with hot-reload)"
	@echo ""
	@echo "Run these commands in separate terminals:"
	@echo "  Terminal 1: $(UV) run $(PYTHON) -m studio.server --tasks-dir $(TASKS_DIR) --port $(PORT)"
	@echo "  Terminal 2: cd $(STUDIO_FRONTEND_DIR) && npm run dev"

.PHONY: studio-clean
studio-clean: ## Clean Studio frontend build artifacts
	@echo "🧹 Cleaning Studio frontend build..."
	rm -rf $(STUDIO_BUILD_DIR)
	rm -rf $(STUDIO_FRONTEND_DIR)/node_modules
	rm -rf $(STUDIO_FRONTEND_DIR)/.svelte-kit

########################################################################################################################
# TESTING
########################################################################################################################

.PHONY: test
test: ## Run tests
	$(UV) run $(PYTEST)

.PHONY: test-verbose
test-verbose: ## Run tests in verbose mode
	$(UV) run $(PYTEST) -v

.PHONY: test-coverage
test-coverage: ## Run tests with coverage
	$(UV) run $(PYTEST) --cov=sygra --cov-report=term --cov-report=xml

########################################################################################################################
# DOCUMENTATION
########################################################################################################################

.PHONY: docs
docs: ## Generate documentation
	$(UV) run mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	$(UV) run mkdocs serve

########################################################################################################################
# BUILDING & PUBLISHING
########################################################################################################################

.PHONY: build
build: ## Build package
	$(UV) run $(PYTHON) -m build

.PHONY: clean
clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -delete
	find . -name '.DS_Store' -delete

.PHONY: ci
ci: check-format check-lint test ## Run CI tasks (format, lint, test)

# Default target
.DEFAULT_GOAL := help
