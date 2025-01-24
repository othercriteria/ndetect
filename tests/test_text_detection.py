import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, List
from unittest.mock import Mock, create_autospec, patch

import pytest

from ndetect.analysis import FileAnalyzer
from ndetect.logging import StructuredLogger
from ndetect.models import FileAnalyzerConfig, TextFile
from ndetect.text_detection import cleanup_resources, scan_paths


def test_file_analyzer_with_invalid_extension(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = create_file_with_content("test.bin", "Hello, World!")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_valid_text(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = create_file_with_content("test.txt", "Hello, World!")
    result = analyzer.analyze_file(file_path)
    assert result is not None


def test_file_analyzer_with_binary_content(tmp_path: Path) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.txt"
    with file_path.open("wb") as f:
        f.write(bytes([0x00, 0x01, 0x02, 0x03]))
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_custom_extensions(tmp_path: Path) -> None:
    file_path = tmp_path / "test.xyz"
    file_path.write_text("Hello, World!")

    default_analyzer = FileAnalyzer(FileAnalyzerConfig())
    assert default_analyzer.analyze_file(file_path) is None

    custom_analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions={".xyz"}))
    assert custom_analyzer.analyze_file(file_path) is not None


def test_file_analyzer_with_low_printable_ratio(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"
    # Create a string with >50% (but <80%) printable characters
    content = "Hello\x00\x00World\x00!"
    file_path.write_bytes(content.encode("utf-8"))

    strict_analyzer = FileAnalyzer(FileAnalyzerConfig())
    assert strict_analyzer.analyze_file(file_path) is None

    lenient_analyzer = FileAnalyzer(FileAnalyzerConfig(min_printable_ratio=0.5))
    assert lenient_analyzer.analyze_file(file_path) is not None


def test_file_analyzer_empty_file(tmp_path: Path) -> None:
    """Test analyzer with empty file."""
    # Test with default config (skip empty files)
    default_analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")
    result = default_analyzer.analyze_file(file_path)
    assert result is None  # Empty files are skipped by default

    # Test with skip_empty=False
    include_empty_analyzer = FileAnalyzer(FileAnalyzerConfig(skip_empty=False))
    result = include_empty_analyzer.analyze_file(file_path)
    assert result is not None
    assert result.size == 0


def test_file_analyzer_very_large_file(tmp_path: Path) -> None:
    """Test analyzer with file larger than read buffer."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "large.txt"
    # Create file larger than 8KB buffer
    content = "x" * 10000
    file_path.write_text(content)
    result = analyzer.analyze_file(file_path)
    assert result is not None
    assert result.size == 10000


def test_file_analyzer_with_unicode_content(tmp_path: Path) -> None:
    """Test analyzer with various Unicode characters."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "unicode.txt"
    # Mix of ASCII and Unicode characters
    content = "Hello, 世界! ñ č ß 🌍"
    file_path.write_text(content)
    result = analyzer.analyze_file(file_path)
    assert result is not None


def test_file_analyzer_with_null_bytes(tmp_path: Path) -> None:
    """Test analyzer with null bytes in content."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions={".txt"}))
    file_path = tmp_path / "test.txt"
    # Create content where null bytes make up >20% of the content
    content = "Hi\x00\x00\x00\x00\x00World"  # 5 nulls in 12 chars
    file_path.write_bytes(content.encode("utf-8"))
    result = analyzer.analyze_file(file_path)
    assert result is None


def test_file_analyzer_with_permission_error(tmp_path: Path) -> None:
    """Test analyzer with unreadable file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "noperm.txt"
    file_path.write_text("test")
    file_path.chmod(0o000)  # Remove all permissions
    result = analyzer.analyze_file(file_path)
    assert result is None
    file_path.chmod(0o666)  # Restore permissions for cleanup


def test_file_analyzer_with_custom_printable_ratio(tmp_path: Path) -> None:
    """Test analyzer with different printable ratio thresholds."""
    # Create content where ~60% is printable (6 printable chars, 4 non-printable)
    content = "Hello\x00\x00\x00\x00W"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content.encode("utf-8"))

    # Test with different thresholds
    strict = FileAnalyzer(
        FileAnalyzerConfig(min_printable_ratio=0.8, allowed_extensions={".txt"})
    )
    lenient = FileAnalyzer(
        FileAnalyzerConfig(min_printable_ratio=0.5, allowed_extensions={".txt"})
    )

    assert strict.analyze_file(file_path) is None  # Should fail 80% threshold
    assert lenient.analyze_file(file_path) is not None  # Should pass 50% threshold


def test_file_analyzer_with_invalid_utf8(tmp_path: Path) -> None:
    """Test analyzer with invalid UTF-8 content."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.txt"
    # Write invalid UTF-8 bytes
    file_path.write_bytes(b"\xff\xfe\xfd")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_mixed_extensions(tmp_path: Path) -> None:
    """Test analyzer with mixed case extensions."""
    content = "Hello, World!"
    config = FileAnalyzerConfig(allowed_extensions={".txt", ".TXT"})
    analyzer = FileAnalyzer(config)

    # Test different case variations
    file1 = tmp_path / "test.txt"
    file2 = tmp_path / "test.TXT"
    file3 = tmp_path / "test.Txt"

    file1.write_text(content)
    file2.write_text(content)
    file3.write_text(content)

    assert analyzer.analyze_file(file1) is not None
    assert analyzer.analyze_file(file2) is not None
    assert analyzer.analyze_file(file3) is not None


def test_file_analyzer_with_empty_extensions_set(tmp_path: Path) -> None:
    """Test analyzer with empty allowed extensions set."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions=set()))
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_symlink(tmp_path: Path) -> None:
    """Test analyzer with symbolic links."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file
    original = tmp_path / "original.txt"
    original.write_text("Hello, World!")

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    result = analyzer.analyze_file(link)
    assert result is not None
    assert result.path == link


@pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0])
def test_file_analyzer_printable_ratio_bounds(tmp_path: Path, ratio: float) -> None:
    """Test analyzer with boundary values for printable ratio."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(min_printable_ratio=ratio))
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    result = analyzer.analyze_file(file_path)
    assert (result is not None) == (ratio <= 1.0)


def test_file_analyzer_with_symlink_loop(tmp_path: Path) -> None:
    """Test analyzer with circular symbolic links."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create a directory for our loop
    loop_dir = tmp_path / "loop"
    loop_dir.mkdir()

    # Create original file
    original = loop_dir / "original.txt"
    original.write_text("Hello, World!")

    # Create a chain of symlinks that forms a loop
    link1 = loop_dir / "link1.txt"
    link2 = loop_dir / "link2.txt"
    link3 = loop_dir / "link3.txt"

    link1.symlink_to(original)
    link2.symlink_to(link1)
    link3.symlink_to(link2)
    # Create the loop
    original.unlink()
    original.symlink_to(link3)

    # Should handle the loop gracefully
    result = analyzer.analyze_file(link1)
    assert result is None  # Should fail safely when encountering a loop


def test_file_analyzer_with_broken_symlink(tmp_path: Path) -> None:
    """Test analyzer with broken symbolic links."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create a symlink to a non-existent file
    link = tmp_path / "broken_link.txt"
    nonexistent = tmp_path / "nonexistent.txt"
    link.symlink_to(nonexistent)

    result = analyzer.analyze_file(link)
    assert result is None


def test_file_analyzer_with_nested_symlinks(tmp_path: Path) -> None:
    """Test analyzer with nested symbolic links."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file
    original = tmp_path / "original.txt"
    original.write_text("Hello, World!")

    # Create a chain of symlinks
    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"
    link3 = tmp_path / "link3.txt"

    link1.symlink_to(original)
    link2.symlink_to(link1)
    link3.symlink_to(link2)

    result = analyzer.analyze_file(link3)
    assert result is not None


def test_file_analyzer_with_relative_symlinks(tmp_path: Path) -> None:
    """Test analyzer with relative symbolic links."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create nested directory structure
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir1" / "dir2"
    dir2.mkdir(parents=True)

    # Create original file
    original = dir1 / "original.txt"
    original.write_text("Hello, World!")

    # Create relative symlink from dir2 to original
    link = dir2 / "link.txt"
    link.symlink_to("../original.txt")

    result = analyzer.analyze_file(link)
    assert result is not None
    assert result.path == link
    assert result.size == len("Hello, World!")


def test_file_analyzer_with_symlink_to_directory(tmp_path: Path) -> None:
    """Test analyzer with symlinks to directories containing target files."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create directory structure
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    # Create file in source directory
    test_file = source_dir / "test.txt"
    test_file.write_text("Hello, World!")

    # Create symlink to directory
    dir_link = target_dir / "source_link"
    dir_link.symlink_to(source_dir)

    # Try to analyze file through directory symlink
    linked_file = dir_link / "test.txt"
    result = analyzer.analyze_file(linked_file)
    assert result is not None
    assert result.path == linked_file
    assert result.size == len("Hello, World!")


def test_scan_paths_with_max_workers(tmp_path: Path) -> None:
    """Test scanning with custom number of workers."""
    # Create multiple test files
    for i in range(5):
        file = tmp_path / f"test{i}.txt"
        file.write_text(f"Content {i}")

    # Test with single worker
    files1 = scan_paths([str(tmp_path)], max_workers=1)
    assert len(files1) == 5

    # Test with multiple workers
    files2 = scan_paths([str(tmp_path)], max_workers=2)
    assert len(files2) == 5

    # Paths should be the same regardless of worker count
    paths1 = {f.path for f in files1}
    paths2 = {f.path for f in files2}
    assert paths1 == paths2


@pytest.mark.skipif(os.name == "nt", reason="Requires Unix-like OS")
def test_symlink_permissions(tmp_path: Path) -> None:
    """Test symlink with different permission scenarios."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file with restricted permissions
    original = tmp_path / "restricted.txt"
    original.write_text("Secret content")
    original.chmod(0o000)

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    try:
        result = analyzer.analyze_file(link)
        assert result is None
    finally:
        # Restore permissions for cleanup
        original.chmod(0o644)


def test_cleanup_resources_normal_shutdown() -> None:
    """Test cleanup with normal executor shutdown."""
    executor = ProcessPoolExecutor(max_workers=1)
    mock_logger = Mock()

    with patch("ndetect.text_detection.logger", mock_logger):
        cleanup_resources(executor)

    # Verify no error logs were created
    mock_logger.error_with_fields.assert_not_called()


def test_cleanup_resources_with_error() -> None:
    """Test cleanup when executor shutdown raises an exception."""
    executor = ProcessPoolExecutor(max_workers=1)
    mock_logger = Mock()

    # Mock the shutdown method to raise an exception
    with patch.object(
        executor, "shutdown", side_effect=RuntimeError("Shutdown failed")
    ):
        with patch("ndetect.text_detection.logger", mock_logger):
            cleanup_resources(executor)

    # Verify error was logged
    mock_logger.error_with_fields.assert_called_once()
    call_args = mock_logger.error_with_fields.call_args[1]
    assert call_args["operation"] == "cleanup"
    assert call_args["error_type"] == "RuntimeError"
    assert "Shutdown failed" in call_args["error_message"]


def failing_analyze_for_test(*args: Any) -> None:
    """Test function that always raises an error."""
    raise RuntimeError("Processing failed")


def test_scan_paths_cleanup_after_exception(tmp_path: Path) -> None:
    """Test that cleanup is called even when scanning fails."""
    # Create enough files to trigger parallel processing
    for i in range(10):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_text(f"test content {i}")

    mock_cleanup = Mock()
    mock_logger = create_autospec(StructuredLogger)

    with (
        patch("ndetect.text_detection.cleanup_resources", mock_cleanup),
        patch(
            "ndetect.text_detection._analyze_file", side_effect=ValueError("Test error")
        ),
        patch("ndetect.text_detection.get_logger", return_value=mock_logger),
    ):
        result = scan_paths([str(tmp_path)])

    # Verify cleanup was called and no files were processed
    assert mock_cleanup.call_count == 1, "Cleanup should be called exactly once"
    assert len(result) == 0, "Expected no successfully processed files"
    assert mock_logger.error_with_fields.call_count > 0, "Expected error logs"


def test_scan_paths_sequential_processing(
    create_test_files: List[Path],
) -> None:
    """Test sequential processing (small number of files)."""
    files = create_test_files  # Use all test files

    cleanup_called = False

    def mock_cleanup(*args: Any) -> None:
        nonlocal cleanup_called
        cleanup_called = True

    with patch("ndetect.text_detection.cleanup_resources", mock_cleanup):
        result = scan_paths([str(files[0].parent)])

        assert not cleanup_called
        assert len(result) == 3  # Updated to match actual number of files
        assert all(isinstance(f, TextFile) for f in result)


def test_scan_paths_with_worker_limit(tmp_path: Path) -> None:
    """Test scanning with worker limit and verify cleanup."""
    for i in range(20):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_text(f"test content {i}")

    with ProcessPoolExecutor(max_workers=2) as executor:
        original_process_count = len(multiprocessing.active_children())
        result = scan_paths([str(tmp_path)], max_workers=2, cleanup_timeout=2.0)

        assert len(result) == 20
        cleanup_resources(executor, timeout=2.0)

        final_process_count = len(multiprocessing.active_children())
        assert final_process_count <= original_process_count


def test_process_cleanup_on_error(tmp_path: Path) -> None:
    """Test that processes are cleaned up even when errors occur."""
    for i in range(20):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_text(f"test content {i}")

    original_process_count = len(multiprocessing.active_children())

    with patch("ndetect.text_detection._analyze_file", failing_analyze_for_test):
        scan_paths([str(tmp_path)], max_workers=2)
        time.sleep(0.5)

        final_process_count = len(multiprocessing.active_children())
        assert final_process_count <= original_process_count


def test_cleanup_resources_timeout() -> None:
    """Test cleanup with timeout."""
    executor = ProcessPoolExecutor(max_workers=1)
    mock_logger = Mock()

    # Create a mock process that appears to be running
    mock_process = Mock()
    mock_process.terminate = Mock()
    mock_process.join = Mock()

    def mock_active_children() -> List[Any]:
        return [mock_process]  # Simulate a process that hasn't terminated

    def slow_shutdown(*args: Any, **kwargs: Any) -> None:
        # Simulate completed shutdown but leave process running
        pass

    with patch("multiprocessing.active_children", mock_active_children):
        with patch.object(executor, "shutdown", side_effect=slow_shutdown):
            with patch("ndetect.text_detection.logger", mock_logger):
                # Use very short timeout to trigger condition quickly
                cleanup_resources(executor, timeout=0.1)

    # Verify timeout warning was logged
    mock_logger.warning_with_fields.assert_called_with(
        "Timeout during executor shutdown, forcing termination",
        operation="cleanup",
        timeout=0.1,
    )
    # Verify process termination was attempted
    mock_process.terminate.assert_called_once()
    mock_process.join.assert_called_once()


def test_cleanup_resources_keyboard_interrupt() -> None:
    """Test cleanup when interrupted."""
    executor = ProcessPoolExecutor(max_workers=1)
    mock_logger = Mock()

    def interrupt_shutdown(*args: Any, **kwargs: Any) -> None:
        raise KeyboardInterrupt()

    with patch.object(executor, "shutdown", side_effect=interrupt_shutdown):
        with patch("ndetect.text_detection.logger", mock_logger):
            cleanup_resources(executor)

    # Verify interrupt warning was logged
    mock_logger.warning_with_fields.assert_called_with(
        "Cleanup interrupted, ensuring process termination", operation="cleanup"
    )


def test_cleanup_resources_with_context() -> None:
    """Test cleanup using context manager."""
    with ProcessPoolExecutor(max_workers=2) as executor:
        original_count = len(multiprocessing.active_children())

        # Simulate some work
        executor.submit(time.sleep, 0.1)

        cleanup_resources(executor)
        time.sleep(0.5)  # Allow time for cleanup

        final_count = len(multiprocessing.active_children())
        assert final_count <= original_count
