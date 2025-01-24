import builtins
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional
from unittest.mock import patch

import pytest

from ndetect.exceptions import FileOperationError, PermissionError
from ndetect.models import RetentionConfig
from ndetect.operations import (
    MoveOperation,
    delete_files,
    execute_moves,
    prepare_moves,
    select_keeper,
)


def test_select_keeper_newest(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test selecting newest file as keeper."""
    # Create files
    file1 = create_file_with_content("old.txt", "old")
    file2 = create_file_with_content("new.txt", "new")

    # Set timestamps after creation
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    config = RetentionConfig(strategy="newest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file2


def test_select_keeper_priority_paths(
    create_file_with_content: Callable[[str, str], Path],
    tmp_path: Path,
) -> None:
    """Test priority paths in keeper selection."""
    # Create directory structure
    important = tmp_path / "important"
    other = tmp_path / "other"
    important.mkdir()
    other.mkdir()

    # Create test files using fixture
    file1 = create_file_with_content("important/test1.txt", "content")
    file2 = create_file_with_content("other/test2.txt", "content")

    config = RetentionConfig(
        strategy="newest", priority_paths=["important/*"], priority_first=True
    )
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_non_interactive_mode_with_retention(
    tmp_path: Path, create_file_with_content: Callable[[str, str], Path]
) -> None:
    """Test non-interactive mode with retention config."""
    # Create test files
    file1 = create_file_with_content("test1.txt", "test content")
    file2 = create_file_with_content("test2.txt", "test content")

    # Set timestamps after creation
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    holding_dir = tmp_path / "duplicates"
    holding_dir.mkdir(parents=True, exist_ok=True)

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        retention_config=RetentionConfig(strategy="newest"),
    )
    assert len(moves) == 1
    assert moves[0].source == file1
    assert moves[0].destination == holding_dir / file1.name


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


def test_delete_files_permission_error(tmp_path: Path) -> None:
    """Test handling of permission errors during file deletion."""
    file = tmp_path / "test.txt"
    file.write_text("test content")

    def mock_unlink(*args: Any) -> None:
        raise builtins.PermissionError("Permission denied")

    with (
        patch.object(Path, "unlink", mock_unlink),
        pytest.raises(
            PermissionError, match=f"delete failed for {file}.*Permission denied"
        ),
    ):
        delete_files([file])

    # Verify file still exists after failed deletion
    assert file.exists()


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


def test_select_keeper_oldest(tmp_path: Path) -> None:
    """Test selecting oldest file as keeper."""
    file1 = tmp_path / "old.txt"
    file2 = tmp_path / "new.txt"

    file1.write_text("old")
    file2.write_text("new")

    # Set different modification times
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    config = RetentionConfig(strategy="oldest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_select_keeper_largest(tmp_path: Path) -> None:
    """Test selecting largest file as keeper."""
    file1 = tmp_path / "small.txt"
    file2 = tmp_path / "large.txt"

    file1.write_text("small")
    file2.write_text("large content")

    config = RetentionConfig(strategy="largest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file2


def test_select_keeper_smallest(tmp_path: Path) -> None:
    """Test selecting smallest file as keeper."""
    file1 = tmp_path / "small.txt"
    file2 = tmp_path / "large.txt"

    file1.write_text("small")
    file2.write_text("large content")

    config = RetentionConfig(strategy="smallest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_select_keeper_shortest_path_with_base_dir(tmp_path: Path) -> None:
    """Test selecting file with shortest path relative to base_dir."""
    nested_dir = tmp_path / "nested" / "path"
    nested_dir.mkdir(parents=True)

    file1 = tmp_path / "direct.txt"
    file2 = nested_dir / "nested.txt"

    file1.write_text("content")
    file2.write_text("content")

    config = RetentionConfig(strategy="shortest_path")
    keeper = select_keeper([file1, file2], config, base_dir=tmp_path)
    assert keeper == file1


def test_select_keeper_shortest_path_without_base_dir(tmp_path: Path) -> None:
    """Test selecting file with shortest absolute path."""
    nested_dir = tmp_path / "nested" / "path"
    nested_dir.mkdir(parents=True)

    file1 = tmp_path / "direct.txt"
    file2 = nested_dir / "nested.txt"

    file1.write_text("content")
    file2.write_text("content")

    config = RetentionConfig(strategy="shortest_path")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_select_keeper_empty_files() -> None:
    """Test selecting keeper with empty file list."""
    config = RetentionConfig(strategy="newest")
    with pytest.raises(ValueError, match="No files provided"):
        select_keeper([], config)


def test_select_keeper_invalid_strategy_validation(tmp_path: Path) -> None:
    """Test that RetentionConfig validates strategies."""
    with pytest.raises(ValueError, match="Invalid strategy. Must be one of:"):
        RetentionConfig(strategy="invalid_strategy")


def test_select_keeper_all_strategies(tmp_path: Path) -> None:
    """Test that all valid strategies work without error."""
    file1 = tmp_path / "test1.txt"
    file1.write_text("content")

    for strategy in RetentionConfig.VALID_STRATEGIES:
        config = RetentionConfig(strategy=strategy)
        keeper = select_keeper([file1], config)
        assert keeper == file1


def test_prepare_moves_with_retention_config(tmp_path: Path) -> None:
    """Test prepare_moves respects retention config when preparing moves."""
    # Create test files with different timestamps
    file1 = tmp_path / "old.txt"
    file2 = tmp_path / "new.txt"
    file1.write_text("old content")
    file2.write_text("new content")

    # Set file2 as newer
    current_time = time.time()
    os.utime(file1, (current_time - 100, current_time - 100))
    os.utime(file2, (current_time, current_time))

    # Configure retention to keep newest
    retention_config = RetentionConfig(strategy="newest")
    holding_dir = tmp_path / "duplicates"

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=True,
        retention_config=retention_config,
    )

    # Verify only the older file is moved
    assert len(moves) == 1, "Should only move the older file"
    assert moves[0].source == file1, "Should move the older file"
    assert moves[0].destination == holding_dir / "old.txt"
    assert not moves[0].executed, "Move should not be marked as executed yet"


def test_execute_moves_updates_status(tmp_path: Path) -> None:
    """Test execute_moves properly updates move operation status."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Create move operations
    moves = [
        MoveOperation(
            source=file1,
            destination=dest_dir / "test1.txt",
            group_id=1,
            timestamp=datetime.now(),
            executed=False,
        ),
        MoveOperation(
            source=file2,
            destination=dest_dir / "test2.txt",
            group_id=1,
            timestamp=datetime.now(),
            executed=False,
        ),
    ]

    # Execute moves and verify status
    execute_moves(moves)

    assert all(
        move.executed for move in moves
    ), "All moves should be marked as executed"
    assert not file1.exists(), "Source file1 should be moved"
    assert not file2.exists(), "Source file2 should be moved"
    assert (dest_dir / "test1.txt").exists(), "Destination file1 should exist"
    assert (dest_dir / "test2.txt").exists(), "Destination file2 should exist"


def test_prepare_moves_respects_existing_keeper(
    create_test_files: List[Path], duplicates_dir: Path
) -> None:
    """Test that prepare_moves doesn't override an existing keeper selection."""
    files = create_test_files[:2]  # Get first two files with different timestamps
    holding_dir = duplicates_dir
    retention_config = RetentionConfig(strategy="newest")

    keeper_selections = []

    def mock_select_keeper(
        files: List[Path], config: RetentionConfig, base_dir: Optional[Path] = None
    ) -> Path:
        selected = files[1]  # Select newer file
        keeper_selections.append(selected)
        return selected

    with patch("ndetect.operations.select_keeper", side_effect=mock_select_keeper):
        moves = prepare_moves(
            files=files,
            holding_dir=holding_dir,
            retention_config=retention_config,
        )

        assert len(keeper_selections) == 1, "Keeper should only be selected once"
        assert len(moves) == 1, "Should only create one move"
        assert moves[0].source == files[0], "Should move older file"
