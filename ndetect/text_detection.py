"""Text file detection and scanning functionality."""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from typing import Iterator, List, Optional, Set

from ndetect.analysis import FileAnalyzer, FileAnalyzerConfig
from ndetect.models import TextFile

logger = logging.getLogger(__name__)


def _analyze_file(args: tuple[Path, FileAnalyzerConfig]) -> Optional[TextFile]:
    """Worker function for parallel processing."""
    path, config = args
    analyzer = FileAnalyzer(config)
    return analyzer.analyze_file(path)


def _collect_files(paths: List[str]) -> Iterator[Path]:
    """Collect all files from given paths."""
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from path.rglob("*")


def scan_paths(
    paths: List[str],
    min_printable_ratio: float = 0.8,
    num_perm: int = 128,
    shingle_size: int = 5,
    allowed_extensions: Optional[Set[str]] = None,
    max_workers: Optional[int] = None,
) -> List[TextFile]:
    """
    Scan paths in parallel and return a list of TextFile instances.

    Args:
        paths: List of paths to scan
        min_printable_ratio: Minimum ratio of printable characters
        num_perm: Number of permutations for MinHash
        shingle_size: Size of shingles to use
        allowed_extensions: Set of allowed file extensions
        max_workers: Maximum number of worker processes (defaults to CPU count)

    Returns:
        List of TextFile instances for valid text files
    """
    # Default to using all CPU cores
    if max_workers is None:
        max_workers = cpu_count()

    config = FileAnalyzerConfig(
        min_printable_ratio=min_printable_ratio,
        num_perm=num_perm,
        shingle_size=shingle_size,
        allowed_extensions=allowed_extensions,
    )

    # Collect all files first
    all_files = list(_collect_files(paths))
    text_files: List[TextFile] = []

    # Process files in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for all files
        future_to_path = {
            executor.submit(_analyze_file, (path, config)): path for path in all_files
        }

        # Process results as they complete
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                if result is not None:
                    text_files.append(result)
                    logger.debug(f"Processed {path}")
            except Exception as e:
                logger.warning(f"Error processing {path}: {e}")

    return text_files
