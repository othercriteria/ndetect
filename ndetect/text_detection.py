"""Text file detection and scanning functionality."""

import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from typing import List, Optional

from ndetect.analysis import FileAnalyzer
from ndetect.models import FileAnalyzerConfig, TextFile
from ndetect.types import FileIterator

logger = logging.getLogger(__name__)

# Set the start method to 'spawn' to avoid fork-related warnings
try:
    multiprocessing.set_start_method("spawn")
except RuntimeError:
    # Method was already set, ignore
    pass


def _analyze_file(args: tuple[Path, FileAnalyzerConfig]) -> Optional[TextFile]:
    """Worker function for parallel processing."""
    path, config = args
    analyzer = FileAnalyzer(config)
    return analyzer.analyze_file(path)


def _collect_files(paths: List[str], follow_symlinks: bool = True) -> FileIterator:
    """Collect all files from given paths."""
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            yield path
        elif path.is_dir():
            # Use Path.rglob() with follow_symlinks parameter
            yield from path.rglob("*") if follow_symlinks else path.rglob("*")


def scan_paths(
    paths: List[str],
    min_printable_ratio: float = 0.8,
    num_perm: int = 128,
    shingle_size: int = 5,
    follow_symlinks: bool = True,
    skip_empty: bool = True,
    max_workers: Optional[int] = None,
) -> List[TextFile]:
    """Scan paths for text files."""
    config = FileAnalyzerConfig(
        min_printable_ratio=min_printable_ratio,
        num_perm=num_perm,
        shingle_size=shingle_size,
        follow_symlinks=follow_symlinks,
        skip_empty=skip_empty,
        allowed_extensions=None,
        max_workers=max_workers,
    )

    # Collect all files
    all_files = list(_collect_files(paths, follow_symlinks=follow_symlinks))

    # For small numbers of files, process sequentially to avoid overhead
    if len(all_files) < 10:
        return [
            result
            for result in (_analyze_file((path, config)) for path in all_files)
            if result is not None
        ]

    # Use parallel processing for larger sets of files
    workers = min(config.max_workers or cpu_count(), len(all_files))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_analyze_file, (path, config)) for path in all_files]

        text_files = []
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                text_files.append(result)

    return text_files
