"""File analysis functionality for ndetect."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from ndetect.models import TextFile


@dataclass
class FileAnalyzerConfig:
    """Configuration for file analysis."""

    min_printable_ratio: float = 0.8
    num_perm: int = 128
    shingle_size: int = 5
    allowed_extensions: Optional[Set[str]] = None

    def __post_init__(self) -> None:
        if self.allowed_extensions is None:
            self.allowed_extensions = {".txt", ".md", ".log", ".csv"}


class FileAnalyzer:
    """Analyzes files for text content and generates MinHash signatures."""

    def __init__(self, config: FileAnalyzerConfig) -> None:
        """Initialize the analyzer with given configuration."""
        self.config = config

    def analyze_file(self, file_path: Path) -> Optional[TextFile]:
        """
        Analyze a file and return a TextFile instance if it's a valid text file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            TextFile instance if the file is valid, None otherwise
        """
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
        # Check if extension is allowed
        if (
            self.config.allowed_extensions is not None
            and file_path.suffix.lower() not in self.config.allowed_extensions
        ):
            return False

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
