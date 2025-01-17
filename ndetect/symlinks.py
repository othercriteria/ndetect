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
                if not path.exists():
                    return None
                if self.config.base_dir and not self._is_within_base_dir(path):
                    return None
                return path

            # Start resolution chain
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
                if self.config.base_dir and not self._is_within_base_dir(current):
                    return None
                return current

            # Get the target and resolve it
            target = current.readlink()
            if not target.is_absolute():
                target = (current.parent / target).resolve(strict=False)

            # Check base directory containment
            if self.config.base_dir and not self._is_within_base_dir(target):
                return None

            return self._resolve_chain(target, depth + 1)

        except OSError:
            return None

    def _is_within_base_dir(self, path: Path) -> bool:
        """Check if path is within allowed base directory."""
        if not self.config.base_dir:
            return True

        try:
            abs_path = path.resolve(strict=False)
            abs_base = self.config.base_dir.resolve(strict=False)

            return str(abs_path).startswith(str(abs_base))
        except OSError:
            return False


def resolve_symlink(path: Path, max_depth: int = 10) -> Optional[Path]:
    """Helper function to resolve a symlink with basic settings."""
    handler = SymlinkHandler(SymlinkConfig(max_depth=max_depth))
    return handler.resolve(path)
