import builtins
import os
import shutil
from pathlib import Path
from typing import Any, List

import pytest
from rich.console import Console

from ndetect.cli import handle_non_interactive_mode
from ndetect.exceptions import FileOperationError, PermissionError
from ndetect.models import RetentionConfig
from ndetect.operations import MoveOperation, delete_files, select_keeper


def test_select_keeper_newest(tmp_path: Path) -> None:
    """Test selecting newest file as keeper."""
    # Create files with different timestamps
    file1 = tmp_path / "old.txt"
    file2 = tmp_path / "new.txt"

    file1.write_text("old")
    file2.write_text("new")

    # Set different modification times
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    config = RetentionConfig(strategy="newest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file2


def test_select_keeper_priority_paths(tmp_path: Path) -> None:
    """Test priority paths in keeper selection."""
    important = tmp_path / "important"
    other = tmp_path / "other"
    important.mkdir()
    other.mkdir()

    file1 = important / "test1.txt"
    file2 = other / "test2.txt"
    file1.write_text("content")
    file2.write_text("content")

    config = RetentionConfig(
        strategy="newest", priority_paths=["important/*"], priority_first=True
    )
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_non_interactive_mode_with_retention(
    tmp_path: Path, duplicates_dir: Path, monkeypatch: Any
) -> None:
    """Test non-interactive mode with retention config."""
    # Create test directory structure
    important = tmp_path / "important"
    other = tmp_path / "other"
    important.mkdir()
    other.mkdir()

    # Create test files
    file1 = important / "test1.txt"
    file2 = other / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    retention_config = RetentionConfig(
        strategy="newest",
        priority_paths=["important/*"],
        priority_first=True,
    )

    # Mock execute_moves to simulate success
    def mock_execute_moves(moves: List[MoveOperation]) -> None:
        # Actually perform the moves for the test
        for move in moves:
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.destination))

    monkeypatch.setattr("ndetect.cli.execute_moves", mock_execute_moves)

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],  # Pass paths instead of text_files
        threshold=0.5,
        base_dir=tmp_path,
        holding_dir=duplicates_dir,
        retention_config=retention_config,
    )
    assert result == 0


def test_delete_files(tmp_path: Path) -> None:
    """Test deleting files."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    files = [file1, file2]
    delete_files(files)

    # Verify files were deleted
    assert not file1.exists()
    assert not file2.exists()


def test_delete_files_permission_error(tmp_path: Path, monkeypatch: Any) -> None:
    """Test handling of permission errors during delete."""
    file = tmp_path / "test.txt"
    file.write_text("content")

    def mock_unlink(*args: Any) -> None:
        raise builtins.PermissionError("Permission denied")

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(PermissionError) as exc_info:
        delete_files([file])

    error_msg = str(exc_info.value)
    # Check that the error contains the expected components
    assert "delete failed" in error_msg
    assert str(file) in error_msg
    # The original error message is included
    assert "Permission denied" in error_msg


def test_delete_files_empty_list() -> None:
    """Test deleting empty list of files."""
    # Should not raise any errors
    delete_files([])


def test_delete_files_nonexistent(tmp_path: Path) -> None:
    """Test deleting nonexistent files."""
    nonexistent = tmp_path / "nonexistent.txt"

    with pytest.raises(FileOperationError) as exc_info:
        delete_files([nonexistent])

    error_msg = str(exc_info.value)
    assert "delete failed" in error_msg.lower()
    assert str(nonexistent) in error_msg
