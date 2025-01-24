"""Text file detection and scanning functionality."""

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from typing import List, Optional

from ndetect.analysis import FileAnalyzer
from ndetect.logging import get_logger
from ndetect.models import FileAnalyzerConfig, TextFile
from ndetect.types import FileIterator

logger = get_logger()

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
    cleanup_timeout: float = 30.0,
) -> List[TextFile]:
    """Scan paths for text files."""
    logger = get_logger()

    config = FileAnalyzerConfig(
        min_printable_ratio=min_printable_ratio,
        num_perm=num_perm,
        shingle_size=shingle_size,
        follow_symlinks=follow_symlinks,
        skip_empty=skip_empty,
        allowed_extensions=None,
        max_workers=max_workers,
    )

    logger.info_with_fields(
        "Starting file scan",
        operation="scan_start",
        paths=paths,
        config={
            "min_printable_ratio": min_printable_ratio,
            "num_perm": num_perm,
            "shingle_size": shingle_size,
            "follow_symlinks": follow_symlinks,
            "skip_empty": skip_empty,
            "max_workers": max_workers,
        },
    )

    # Collect all files
    start_time = time.perf_counter()
    all_files = list(_collect_files(paths, follow_symlinks=follow_symlinks))
    collection_time = time.perf_counter() - start_time

    logger.info_with_fields(
        "File collection completed",
        operation="collect_files",
        total_files=len(all_files),
        collection_time=collection_time,
    )

    # For small numbers of files, process sequentially to avoid overhead
    if len(all_files) < 10:
        logger.debug_with_fields(
            "Using sequential processing for small file set",
            operation="process_mode",
            mode="sequential",
            file_count=len(all_files),
        )
        results = [
            result
            for result in (_analyze_file((path, config)) for path in all_files)
            if result is not None
        ]
        logger.info_with_fields(
            "Sequential processing completed",
            operation="scan_complete",
            total_input_files=len(all_files),
            valid_text_files=len(results),
            processing_time=time.perf_counter() - start_time,
        )
        return results

    # Use parallel processing for larger sets of files
    workers = min(config.max_workers or cpu_count(), len(all_files))
    logger.debug_with_fields(
        "Using parallel processing",
        operation="process_mode",
        mode="parallel",
        worker_count=workers,
        file_count=len(all_files),
    )

    text_files: List[TextFile] = []
    processed_count = 0
    start_process_time = time.perf_counter()

    executor = ProcessPoolExecutor(max_workers=workers)
    try:
        futures = [executor.submit(_analyze_file, (path, config)) for path in all_files]

        for future in as_completed(futures):
            processed_count += 1
            if processed_count % 100 == 0:  # Log progress every 100 files
                logger.debug_with_fields(
                    "Processing progress",
                    operation="scan_progress",
                    processed_files=processed_count,
                    total_files=len(all_files),
                    valid_files=len(text_files),
                    elapsed_time=time.perf_counter() - start_process_time,
                )

            try:
                result = future.result()
                if result is not None:
                    text_files.append(result)
            except Exception as e:
                logger.error_with_fields(
                    "Error processing file",
                    operation="file_error",
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
    finally:
        cleanup_resources(executor, timeout=cleanup_timeout)

    total_time = time.perf_counter() - start_time
    logger.info_with_fields(
        "File scan completed",
        operation="scan_complete",
        total_input_files=len(all_files),
        valid_text_files=len(text_files),
        total_time=total_time,
        collection_time=collection_time,
        processing_time=total_time - collection_time,
        workers_used=workers,
    )

    return text_files


# ruff: noqa: C901
def cleanup_resources(executor: ProcessPoolExecutor, timeout: float = 30.0) -> None:
    """Ensure proper cleanup of process pool resources.

    Args:
        executor: The ProcessPoolExecutor to clean up
        timeout: Maximum time in seconds to wait for shutdown (default: 30.0)
    """
    try:
        # First attempt graceful shutdown without timeout parameter
        executor.shutdown(wait=True, cancel_futures=True)

        # Additional timeout-based wait for remaining processes
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            remaining = multiprocessing.active_children()
            if not remaining:
                break
            time.sleep(0.1)
        else:
            logger.warning_with_fields(
                "Timeout during executor shutdown, forcing termination",
                operation="cleanup",
                timeout=timeout,
            )
            # Force terminate remaining processes
            for process in multiprocessing.active_children():
                try:
                    process.terminate()
                    # Add explicit join with timeout
                    process.join(timeout=1.0)
                except Exception as e:
                    logger.error_with_fields(
                        "Failed to terminate process during cleanup",
                        operation="cleanup",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        pid=process.pid if hasattr(process, "pid") else None,
                    )

    except KeyboardInterrupt:
        logger.warning_with_fields(
            "Cleanup interrupted, ensuring process termination", operation="cleanup"
        )
        # Handle keyboard interrupt during cleanup
        for process in multiprocessing.active_children():
            try:
                process.terminate()
                process.join(timeout=1.0)
            except Exception as e:
                logger.error_with_fields(
                    "Failed to terminate process during cleanup",
                    operation="cleanup",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    pid=process.pid if hasattr(process, "pid") else None,
                )
    except Exception as e:
        logger.error_with_fields(
            "Error during resource cleanup",
            operation="cleanup",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        # Still try to terminate processes
        for process in multiprocessing.active_children():
            try:
                process.terminate()
                process.join(timeout=1.0)
            except Exception as e:
                logger.error_with_fields(
                    "Failed to terminate process during cleanup",
                    operation="cleanup",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    pid=process.pid if hasattr(process, "pid") else None,
                )
