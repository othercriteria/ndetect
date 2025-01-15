#!/usr/bin/env bash

# Kill mypy daemon if running
if [ -f "$HOME/.dmypy.json" ]; then
  dmypy stop || true
fi
