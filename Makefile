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
	$(UV) sync --extra ui

.PHONY: setup-ui
setup-ui: ## Install development dependencies
	@echo "Installing SyGra UI dependencies"
	$(UV) sync --extra ui

.PHONY: setup-dev
setup-dev: ## Install development dependencies
	@echo "Installing SyGra Core, Extra and Development dependencies"
	$(UV) sync --extra dev --extra ui

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
