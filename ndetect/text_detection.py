from pathlib import Path
from typing import Optional


def is_text_file(
    file_path: Path,
    min_printable_ratio: float = 0.8,
    allowed_extensions: Optional[set[str]] = None,
) -> bool:
    """
    Check if a file is likely to be a text file.

    Args:
        file_path: Path to the file to check
        min_printable_ratio: Minimum ratio of printable characters (default: 0.8)
        allowed_extensions: Set of allowed file extensions (default: {'.txt', '.md', '.log', '.csv'})

    Returns:
        bool: True if the file is likely to be a text file, False otherwise
    """
    if allowed_extensions is None:
        allowed_extensions = {".txt", ".md", ".log", ".csv"}

    # Check file extension
    if file_path.suffix.lower() not in allowed_extensions:
        return False

    try:
        # Try reading the first 8KB of the file
        sample_size = 8 * 1024
        with file_path.open("rb") as f:
            raw_bytes = f.read(sample_size)

        # Try decoding as UTF-8
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return False

        # Count printable characters
        printable_chars = sum(1 for c in content if c.isprintable() or c.isspace())
        ratio = printable_chars / len(content) if content else 0

        return ratio >= min_printable_ratio

    except (IOError, OSError):
        return False 