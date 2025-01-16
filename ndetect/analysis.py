"""File analysis functionality for ndetect."""

from pathlib import Path
from typing import Optional

from ndetect.models import FileAnalyzerConfig, TextFile


class FileAnalyzer:
    """Analyzes files for text content and generates MinHash signatures."""

    def __init__(self, config: FileAnalyzerConfig) -> None:
        """Initialize the analyzer with given configuration."""
        self.config = config

    def _is_valid_symlink(self, file_path: Path) -> bool:
        """Check if symlink is valid and not circular."""
        if not file_path.is_symlink():
            return True

        # Check for circular symlinks
        try:
            real_path = file_path.resolve(strict=True)
            return real_path.exists()
        except (RuntimeError, OSError):
            return False

    def analyze_file(self, file_path: Path) -> Optional[TextFile]:
        """
        Analyze a file and return a TextFile instance if it's a valid text file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            TextFile instance if the file is valid, None otherwise
        """
        # Early validation of symlinks
        if not self._is_valid_symlink(file_path):
            return None

        if not self._is_valid_text_file(file_path):
            return None

        return TextFile.from_path(
            file_path,
            compute_minhash=True,
            num_perm=self.config.num_perm,
            shingle_size=self.config.shingle_size,
        )

    def _is_valid_text_file(self, file_path: Path) -> bool:
        """Check if a file is a valid text file according to configuration."""
        # Check for circular symlinks
        try:
            real_path = file_path.resolve(strict=True)
        except (RuntimeError, OSError):
            return False

        # Check if extension is allowed
        if (
            self.config.allowed_extensions is not None
            and file_path.suffix.lower() not in self.config.allowed_extensions
        ):
            return False

        # If symlinks are disabled and this is a symlink, skip it
        if not self.config.follow_symlinks and file_path.is_symlink():
            return False

        # Skip empty files if configured
        if self.config.skip_empty and real_path.stat().st_size == 0:
            return False

        try:
            with real_path.open("rb") as f:
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
