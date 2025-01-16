#!/usr/bin/env bash

# Print mypy version for debugging
mypy --version

# Start mypy daemon if not running
if ! dmypy status >/dev/null 2>&1; then
  # Clear cache before starting daemon
  rm -rf .mypy_cache
  dmypy start -- --config-file pyproject.toml
fi

# Run type checking
dmypy check .
