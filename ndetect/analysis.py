"""File analysis functionality."""

from pathlib import Path
from typing import Optional

from .exceptions import FileOperationError
from .models import FileAnalyzerConfig, TextFile
from .symlinks import SymlinkConfig, SymlinkHandler

__all__ = ["FileAnalyzer"]


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
            text_file = TextFile.from_path(file_path, compute_minhash=False)
            return text_file.is_valid_text(
                min_printable_ratio=self.config.min_printable_ratio
            )
        except (OSError, FileOperationError):
            return False
