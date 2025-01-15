.PHONY: install test lint format clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	mypy .

format:
	black .
	ruff check --fix .

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
