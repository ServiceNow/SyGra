########################################################################################################################
# VARIABLES
########################################################################################################################

# Define code paths for various operations
CODE_PATHS = grasp tests tasks

# Define paths for JSON files
JSON_PATHS = $(shell find grasp -name "*.json")

# Minimum acceptable pylint score (0.0 - 10.0). CI will fail if below this.
PYLINT_FAIL_UNDER ?= 8.0

########################################################################################################################
# LINT
########################################################################################################################

.PHONY: lint-local
lint-local: lint-flake8-local lint-pylint-local lint-mypy-local ## Run all linters using poetry

.PHONY: lint
lint: ## Run all linters in a controlled environment
	@echo "Running all linters"
	poetry run make lint-local

.PHONY: lint-flake8-local
lint-flake8-local: ## Check code with flake8 using poetry
	@echo "Checking code with flake8"
	poetry run flake8 $(CODE_PATHS)

.PHONY: lint-flake8
lint-flake8: ## Run flake8 in a controlled environment
	poetry run make lint-flake8-local

.PHONY: lint-pylint-local
lint-pylint-local: ## Analyze the code with pylint using poetry
	@echo "Analyzing code with pylint"
	poetry run pylint --jobs 0 --fail-under=$(PYLINT_FAIL_UNDER) $(CODE_PATHS)

.PHONY: lint-pylint
lint-pylint: ## Run pylint in a controlled environment
	poetry run make lint-pylint-local

.PHONY: lint-mypy-local
lint-mypy-local: ## Type-check the code using mypy and poetry
	@echo "Type-checking code with mypy"
	poetry run mypy $(CODE_PATHS)

.PHONY: lint-mypy
lint-mypy: ## Run mypy in a controlled environment
	poetry run make lint-mypy-local

########################################################################################################################
# FORMAT
########################################################################################################################

.PHONY: format-local
format-local: format-black-local format-isort-local ## Run all formatters using poetry

.PHONY: format
format: ## Run all formatters in a controlled environment
	@echo "Running all formatters"
	poetry run make format-local

.PHONY: format-black-local
format-black-local: ## Format the code with black using poetry
	@echo "Formatting code with black"
	poetry run black $(CODE_PATHS)

.PHONY: format-black
format-black: ## Run black in a controlled environment
	poetry run make format-black-local

.PHONY: format-isort-local
format-isort-local: ## Sort imports with isort using poetry
	@echo "Sorting imports with isort"
	poetry run isort $(CODE_PATHS)

.PHONY: format-isort
format-isort: ## Run isort in a controlled environment
	poetry run make format-isort-local

########################################################################################################################
# CHECK FORMATTING
########################################################################################################################

.PHONY: check-format-local
check-format-local: check-format-black-local check-format-isort-local ## Check formatting without modifying files

.PHONY: check-format
check-format: ## Check all formatting in a controlled environment
	@echo "Checking all formatting"
	poetry run make check-format-local

.PHONY: check-format-black-local
check-format-black-local: ## Check black formatting without modifying files
	@echo "Checking black formatting"
	poetry run black --check $(CODE_PATHS)

.PHONY: check-format-black
check-format-black: ## Run black check in a controlled environment
	poetry run make check-format-black-local

.PHONY: check-format-isort-local
check-format-isort-local: ## Check isort formatting without modifying files
	@echo "Checking isort formatting"
	poetry run isort --check --diff $(CODE_PATHS)

.PHONY: check-format-isort
check-format-isort: ## Run isort check in a controlled environment
	poetry run make check-format-isort-local

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
