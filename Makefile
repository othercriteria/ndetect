.PHONY: install test lint format clean lint-md fix-md security check check-all

install:
	pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest

typecheck:
	dmypy check .

lint:
	ruff check .

format:
	ruff check --fix .

lint-md:
	markdownlint "README.md" "CHANGELOG.md" "CONTRIBUTING.md" "SECURITY.md" "docs/**/*.md" ".github/**/*.md"

fix-md:
	markdownlint --fix "README.md" "CHANGELOG.md" "CONTRIBUTING.md" "SECURITY.md" "docs/**/*.md" ".github/**/*.md"

# Security-related targets
security-scan:
	bandit -r ndetect/ -c pyproject.toml

security-deps:
	safety check

security: security-scan security-deps
	@echo "All security checks passed!"

# Comprehensive check targets
check: lint typecheck lint-md
	@echo "All code quality checks passed!"

check-all: check test security
	@echo "All checks and tests passed!"

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
