"""Tests for keeper selection logic."""

import os
import time
from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

import pytest
from rich.console import Console
from rich.prompt import Prompt

from ndetect.models import MoveConfig, RetentionConfig
from ndetect.operations import select_keeper
from ndetect.ui import InteractiveUI


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


def test_select_keeper_invalid_strategy_validation() -> None:
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


def test_select_keeper_with_override(tmp_path: Path) -> None:
    """Test that keeper selection can be overridden by user."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"

    # Create files with different timestamps
    file1.write_text("content")
    file2.write_text("content")
    file3.write_text("content")

    # Set file3 as newest
    current_time = time.time()
    os.utime(file1, (current_time - 200, current_time - 200))
    os.utime(file2, (current_time - 100, current_time - 100))
    os.utime(file3, (current_time, current_time))

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    def mock_ask(prompt: str, choices: Optional[List[str]] = None) -> str:
        if "Select keeper file number" in str(prompt):
            assert choices == [
                "1",
                "2",
                "3",
            ], f"Expected choices [1,2,3], got {choices}"
            return "2"  # Select file2 as keeper
        if "Do you want to select a different keeper?" in str(prompt):
            return "y"
        return ""

    with (
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2, file3])

        assert result is True, "Operation should succeed"

        # Get the files that would be deleted
        mock_delete_call = mock_delete.call_args
        assert mock_delete_call is not None, "delete_files should have been called"
        files_to_delete = mock_delete_call[0][0]

        # Verify file2 is not in deletion list (it's the keeper)
        assert file2 not in files_to_delete, "Keeper file should not be deleted"
        # Verify both other files are in deletion list
        assert file1 in files_to_delete, "file1 should be deleted"
        assert file3 in files_to_delete, "file3 should be deleted"
