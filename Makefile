# Include check.mk for lint and format checks
include check.mk

########################################################################################################################
# VARIABLES
########################################################################################################################

# Python interpreter
PYTHON = python
PYTEST = pytest
POETRY = poetry

########################################################################################################################
# DEVELOPMENT ENVIRONMENT
########################################################################################################################

.PHONY: setup
setup: ## Install core dependencies
	@echo "Installing GraSP core dependencies"
	$(POETRY) install --no-interaction --no-root --without dev,ui

.PHONY: setup-all
setup-all: ## Install core and extra dependencies
	@echo "Installing GraSP Core and extra dependencies"
	$(POETRY) install --no-interaction --no-root --without dev

.PHONY: setup-ui
setup-ui: ## Install development dependencies
	@echo "Installing GraSP UI dependencies"
	$(POETRY) install --no-interaction --no-root --without dev

.PHONY: setup-dev
setup-dev: ## Install development dependencies
	@echo "Installing GraSP Core, Extra and Development dependencies"
	$(POETRY) install --no-interaction --no-root

########################################################################################################################
# TESTING
########################################################################################################################

.PHONY: test
test: ## Run tests
	$(POETRY) run $(PYTEST)

.PHONY: test-verbose
test-verbose: ## Run tests in verbose mode
	$(POETRY) run $(PYTEST) -v

.PHONY: test-coverage
test-coverage: ## Run tests with coverage
	$(POETRY) run $(PYTEST) --cov=grasp --cov-report=term --cov-report=xml

########################################################################################################################
# DOCUMENTATION
########################################################################################################################

.PHONY: docs
docs: ## Generate documentation
	$(POETRY) run mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	$(POETRY) run mkdocs serve

########################################################################################################################
# BUILDING & PUBLISHING
########################################################################################################################

.PHONY: build
build: ## Build package
	$(POETRY) build

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
ci: format lint test ## Run CI tasks (format, lint, test)

# Default target
.DEFAULT_GOAL := help