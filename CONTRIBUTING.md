# Contributing to ndetect

## Development Setup

1. Ensure you have Nix installed with flakes enabled
2. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/ndetect.git
   cd ndetect
   ```

3. Enter the development shell:

   ```bash
   nix develop
   ```

## Code Quality Standards

We use several tools to maintain code quality:

- **Black**: Code formatting
- **Flake8**: Style guide enforcement
- **isort**: Import sorting
- **mypy**: Static type checking
- **pre-commit**: Automated checks before commits

These tools are automatically installed in the development environment and configured via:

- `pyproject.toml`: Black and isort configuration
- `.flake8`: Flake8 configuration
- `.pre-commit-config.yaml`: Pre-commit hooks configuration

## Running Tests

```bash
pytest
```

## Before Submitting a Pull Request

1. Ensure all tests pass
2. Run code quality checks:

   ```bash
   black .
   flake8
   isort .
   mypy .
   ```

3. Commit your changes and ensure pre-commit hooks pass
