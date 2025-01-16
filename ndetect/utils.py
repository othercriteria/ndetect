import shutil
from pathlib import Path
from typing import List

from .exceptions import DiskSpaceError, FileOperationError


def check_disk_space(path: Path, required_bytes: int) -> None:
    """Check if there's enough disk space available."""
    try:
        usage = shutil.disk_usage(path.parent)
        if usage.free < required_bytes:
            raise DiskSpaceError(str(path), required_bytes, usage.free)
    except OSError as e:
        # Handle case where disk usage can't be determined
        raise FileOperationError(str(e), str(path), "check space") from e


def get_total_size(files: List[Path]) -> int:
    """Get total size of files."""
    return sum(f.stat().st_size for f in files)


def format_preview_text(
    text: str, max_lines: int, max_chars: int, truncation_marker: str = "..."
) -> str:
    """
    Format text for preview by applying line and character limits.

    Args:
        text: Input text to format
        max_lines: Maximum number of lines to include
        max_chars: Maximum number of characters in total
        truncation_marker: String to append when text is truncated

    Returns:
        Formatted text respecting the given limits
    """
    if not text:
        return ""

    # Always reserve space for marker unless text is shorter than limit
    marker_space = len(truncation_marker)
    max_content_length = max_chars - marker_space

    # Ensure we have at least enough space for one character plus marker
    if max_content_length < 1:
        return truncation_marker

    # Split into lines
    all_lines = text.splitlines()

    # If text fits completely within limits, return it whole
    content = "\n".join(all_lines[:max_lines])
    if len(content) <= max_chars and len(all_lines) <= max_lines:
        return content

    # Otherwise we need to truncate
    if len(all_lines) == 1:
        # Single line case
        return text[:max_content_length] + truncation_marker

    # Multiple lines case
    result: List[str] = []
    current_length = 0

    for line in all_lines[:max_lines]:
        # Calculate new length including newline if not first line
        new_length = current_length + len(line)
        if result:
            new_length += 1

        if new_length > max_content_length:
            # If we haven't added any lines yet, take at least one character
            if not result and max_content_length > 0:
                return line[:max_content_length] + truncation_marker
            break

        result.append(line)
        current_length = new_length

    content = "\n".join(result)
    # If we couldn't fit anything, just return the marker
    if not content:
        return truncation_marker
    return content + truncation_marker
