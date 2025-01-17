"""Symlink handling and security validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set


@dataclass
class SymlinkConfig:
    """Configuration for symlink handling."""

    follow_symlinks: bool = True
    max_depth: int = 10
    base_dir: Optional[Path] = None


class SymlinkHandler:
    """Handles symlink resolution and security validation."""

    def __init__(self, config: SymlinkConfig) -> None:
        self.config = config
        self._seen_paths: Set[Path] = set()

    def resolve(self, path: Path) -> Optional[Path]:
        """Resolve a symlink with security checks."""
        if not self.config.follow_symlinks:
            return None

        try:
            self._seen_paths.clear()

            # For non-symlinks, just verify existence
            if not path.is_symlink():
                return path if path.exists() else None

            return self._resolve_chain(path, depth=0)

        except OSError:
            return None

    def _resolve_chain(self, current: Path, depth: int) -> Optional[Path]:
        """Recursively resolve symlink chain with security checks."""
        if depth >= self.config.max_depth:
            return None

        try:
            # Check for cycles
            if current in self._seen_paths:
                return None
            self._seen_paths.add(current)

            # Verify existence
            if not current.exists():
                return None

            # If not a symlink, we've reached the end
            if not current.is_symlink():
                return current

            # Get the target
            target = current.readlink()
            if not target.is_absolute():
                target = (current.parent / target).resolve()

            # Check base directory constraint
            if self.config.base_dir:
                try:
                    target.relative_to(self.config.base_dir)
                except ValueError:
                    return None

            return self._resolve_chain(target, depth + 1)

        except OSError:
            return None
