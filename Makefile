.PHONY: install test lint format clean lint-md fix-md security check check-all help

install: ## Install the package in development mode
	pip install -e ".[dev]"

test: ## Run tests
	.venv/bin/python -m pytest

typecheck: ## Run type checking
	dmypy check .

lint: ## Run linting checks
	ruff check .

format: ## Format code using ruff
	ruff check --fix .

lint-md: ## Lint markdown files
	markdownlint "README.md" "CHANGELOG.md" "CONTRIBUTING.md" "SECURITY.md" "docs/**/*.md" ".github/**/*.md"

fix-md: ## Fix markdown lint issues
	markdownlint --fix "README.md" "CHANGELOG.md" "CONTRIBUTING.md" "SECURITY.md" "docs/**/*.md" ".github/**/*.md"

# Security-related targets
security-scan: ## Run security scan using bandit
	bandit -r ndetect/ -c pyproject.toml

security-deps: ## Check dependencies for known security issues
	safety check

security: security-scan security-deps ## Run all security checks
	@echo "All security checks passed!"

# Comprehensive check targets
check: lint typecheck lint-md ## Run code quality checks
	@echo "All code quality checks passed!"

check-all: check test security ## Run all checks and tests
	@echo "All checks and tests passed!"

clean: ## Clean up build artifacts and cache directories
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
