# Contributing to ndetect

## Development Setup

1. Ensure you have Nix installed with flakes enabled
1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/ndetect.git
   cd ndetect
   ```

1. Enter the development shell:

   ```bash
   nix develop
   ```

   This will automatically start the mypy daemon for faster type checking.

## Code Quality Standards

We use several tools to maintain code quality:

- **ruff**: Code formatting, linting, and import sorting
- **mypy/dmypy**: Static type checking with daemon mode for performance
- **pre-commit**: Automated checks before commits

These tools are automatically installed in the development environment and configured via:

- `pyproject.toml`: ruff and mypy configuration
- `.pre-commit-config.yaml`: Pre-commit hooks configuration

### Type Checking with dmypy

The mypy daemon (dmypy) is used for faster type checking:

- Status check: `dmypy status`
- Manual check: `dmypy check .`
- Stop daemon: `dmypy stop`

Helper scripts are provided:

- `./scripts/dev.sh`: Start daemon if needed and run type checking
- `./scripts/cleanup.sh`: Stop the daemon

The daemon is automatically:

- Started when entering the nix shell
- Used by pre-commit hooks
- Configured via settings in pyproject.toml

## Running Tests

```bash
pytest
```

## Before Submitting a Pull Request

1. Ensure all tests pass
1. Run code quality checks:

   ```bash
   black .
   flake8
   isort .
   dmypy check .  # Faster than running mypy directly
   ```

1. Commit your changes and ensure pre-commit hooks pass
