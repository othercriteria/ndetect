#!/usr/bin/env bash

# Start mypy daemon if not running
if ! dmypy status >/dev/null 2>&1; then
  dmypy start -- --config-file pyproject.toml
fi

# Run type checking
dmypy check .
