.PHONY: install test lint format clean lint-md fix-md

install:
	pip install -e ".[dev]"

test:
	pytest

typecheck:
	dmypy check .

lint:
	ruff check .

format:
	ruff check --fix .

lint-md:
	markdownlint "**/*.md"

fix-md:
	markdownlint --fix "**/*.md"

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
