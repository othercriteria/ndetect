import builtins
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import patch

import pytest
from rich.console import Console

from ndetect.cli import handle_non_interactive_mode
from ndetect.exceptions import FileOperationError, PermissionError
from ndetect.logging import get_logger
from ndetect.models import CLIConfig, RetentionConfig
from ndetect.operations import (
    MoveOperation,
    delete_files,
    execute_moves,
    prepare_moves,
    select_keeper,
)
from ndetect.similarity import SimilarityGraph
from ndetect.text_detection import scan_paths


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

    config = CLIConfig(
        paths=[str(tmp_path)],
        mode="non-interactive",
        threshold=0.5,
        base_dir=tmp_path,
        holding_dir=duplicates_dir,
        retention_strategy="newest",
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
    text_files = scan_paths(
        paths=config.paths,
        min_printable_ratio=config.min_printable_ratio,
        num_perm=config.num_perm,
        shingle_size=config.shingle_size,
        follow_symlinks=config.follow_symlinks,
        max_workers=config.max_workers,
    )

    # Create and populate the similarity graph
    graph = SimilarityGraph(threshold=config.threshold)
    graph.add_files(text_files)

    result = handle_non_interactive_mode(
        config=config,
        console=console,
        text_files=text_files,
        graph=graph,
        logger=get_logger(),
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


def test_prepare_moves_respects_existing_keeper(tmp_path: Path) -> None:
    """Test that prepare_moves doesn't override an existing keeper selection."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    # Set different timestamps to make file2 newer
    current_time = time.time()
    os.utime(file1, (current_time - 100, current_time - 100))
    os.utime(file2, (current_time, current_time))

    holding_dir = tmp_path / "duplicates"
    retention_config = RetentionConfig(strategy="newest")

    # Track keeper selections
    keeper_selections = []

    def mock_select_keeper(
        files: List[Path], config: RetentionConfig, base_dir: Optional[Path] = None
    ) -> Path:
        selected = file2  # Always select newer file
        keeper_selections.append(selected)
        return selected

    with patch("ndetect.operations.select_keeper", side_effect=mock_select_keeper):
        moves = prepare_moves(
            files=[file1, file2],
            holding_dir=holding_dir,
            retention_config=retention_config,
        )

        print("\nDebug - prepare_moves keeper selections:")
        for i, keeper in enumerate(keeper_selections, 1):
            print(f"  Selection {i}: {keeper}")

        assert len(keeper_selections) == 1, "Keeper should only be selected once"
        assert len(moves) == 1, "Should only create one move"
        assert moves[0].source == file1, "Should move older file"
