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
            # For non-symlinks, just verify existence
            if not path.is_symlink():
                return path if path.exists() else None

            # Reset seen paths for new resolution
            self._seen_paths.clear()
            return self._resolve_chain(path, depth=0)

        except (OSError, RuntimeError):
            return None

    def _resolve_chain(self, current: Path, depth: int) -> Optional[Path]:
        """Recursively resolve symlink chain with security checks."""
        if depth >= self.config.max_depth:
            return None

        if current in self._seen_paths:
            return None  # Circular reference
        self._seen_paths.add(current)

        if not current.exists():
            return None

        if not current.is_symlink():
            return current

        # Get the target and make it absolute if needed
        target = current.readlink()
        if not target.is_absolute():
            target = (current.parent / target).resolve()

        # Check if target is within base directory if specified
        if self.config.base_dir and not self._is_within_base_dir(target):
            return None

        return self._resolve_chain(target, depth + 1)

    def _is_within_base_dir(self, path: Path) -> bool:
        """Check if path is within base directory."""
        if not self.config.base_dir:
            return True
        try:
            path.relative_to(self.config.base_dir)
            return True
        except ValueError:
            return False
