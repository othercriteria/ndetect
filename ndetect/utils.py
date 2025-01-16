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
