"""File analysis functionality."""

from pathlib import Path
from typing import Optional

from .models import FileAnalyzerConfig, TextFile
from .symlinks import SymlinkConfig, SymlinkHandler

__all__ = ["FileAnalyzer", "resolve_symlink"]


def resolve_symlink(path: Path, max_depth: int = 10) -> Optional[Path]:
    """Resolve a symlink with maximum depth protection."""
    try:
        # For non-symlinks, just verify existence and return
        if not path.is_symlink():
            return path if path.exists() else None

        # For symlinks, follow the chain
        current = path
        seen = set()
        depth = 0

        while depth < max_depth:
            if current in seen:
                return None  # Circular reference
            seen.add(current)

            if not current.exists():
                return None

            if not current.is_symlink():
                return current

            # Get the target and make it absolute if needed
            target = current.readlink()
            if not target.is_absolute():
                target = (current.parent / target).resolve()

            current = target
            depth += 1

        return None  # Max depth exceeded

    except (OSError, RuntimeError):
        return None


class FileAnalyzer:
    """Analyzes files for text content."""

    def __init__(self, config: FileAnalyzerConfig) -> None:
        self.config = config
        self.symlink_handler = SymlinkHandler(
            SymlinkConfig(
                follow_symlinks=config.follow_symlinks,
                max_depth=config.max_symlink_depth,
                base_dir=config.base_dir,
            )
        )

    def analyze_file(self, file_path: Path) -> Optional[TextFile]:
        """Analyze a file and return TextFile if valid."""
        try:
            if not self._is_valid_text_file(file_path):
                return None

            return TextFile.from_path(file_path)
        except OSError:
            return None

    def _is_valid_text_file(self, file_path: Path) -> bool:
        """Check if a file is a valid text file according to configuration."""
        try:
            # Handle symlinks
            if file_path.is_symlink():
                resolved = self.symlink_handler.resolve(file_path)
                if resolved is None:
                    return False
                real_path = resolved
            else:
                if not file_path.exists():
                    return False
                real_path = file_path

            # Check if extension is allowed
            if (
                self.config.allowed_extensions is not None
                and file_path.suffix.lower() not in self.config.allowed_extensions
            ):
                return False

            # Skip empty files if configured
            if self.config.skip_empty and real_path.stat().st_size == 0:
                return False

            # Check text content
            return self._is_valid_text_content(real_path)

        except OSError:
            return False

    def _is_valid_text_content(self, file_path: Path) -> bool:
        """Check if file content is valid text."""
        try:
            with file_path.open("rb") as f:
                raw_bytes = f.read(8 * 1024)  # Read first 8KB

            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return False

            # For empty files, consider them valid text files
            if not content:
                return True

            printable_chars = sum(1 for c in content if c.isprintable() or c.isspace())
            ratio = printable_chars / len(content)

            return ratio >= self.config.min_printable_ratio

        except OSError:
            return False
