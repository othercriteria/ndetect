"""Test interactive delete functionality with retention config."""

import os
import time
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.prompt import Prompt

from ndetect.models import MoveConfig, RetentionConfig
from ndetect.ui import InteractiveUI


def test_handle_delete_with_retention_config(tmp_path: Path) -> None:
    """Test delete handling with retention config."""
    # Create test files with different sizes
    file1 = tmp_path / "small.txt"
    file2 = tmp_path / "large.txt"
    file1.write_text("small")
    file2.write_text("large content")

    # Configure UI with retention config set to keep largest file
    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="largest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Mock both Prompt.ask and Confirm.ask
    with (
        patch.object(Prompt, "ask", return_value="1"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 1
        assert files_to_delete[0] == file1


def test_handle_delete_no_retention_config(tmp_path: Path) -> None:
    """Test delete handling without retention config."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(console=console, move_config=move_config, retention_config=None)

    with (
        patch.object(Prompt, "ask", return_value="1,2"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 2
        assert file1 in files_to_delete
        assert file2 in files_to_delete


def test_handle_delete_retention_empty_selection(tmp_path: Path) -> None:
    """Test delete handling when retention config results in no files to delete."""
    file1 = tmp_path / "test.txt"
    file1.write_text("content")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1])

        assert result is False
        mock_delete.assert_not_called()


def test_handle_delete_retention_priority_paths(tmp_path: Path) -> None:
    """Test delete handling with retention config using priority paths."""
    priority_dir = tmp_path / "priority"
    other_dir = tmp_path / "other"
    priority_dir.mkdir()
    other_dir.mkdir()

    priority_file = priority_dir / "important.txt"
    other_file = other_dir / "normal.txt"
    priority_file.write_text("important content")
    other_file.write_text("normal content")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(
        strategy="newest", priority_paths=["priority/*"], priority_first=True
    )
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch.object(Prompt, "ask", return_value="2"),  # Select the non-priority file
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([priority_file, other_file])

        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 1
        assert files_to_delete[0] == other_file


def test_handle_delete_invalid_selection(tmp_path: Path) -> None:
    """Test handling of invalid file selection input."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(console=console, move_config=move_config, retention_config=None)

    # Test invalid numeric input
    with (
        patch.object(Prompt, "ask", return_value="3"),  # Invalid index
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])
        assert result is False
        mock_delete.assert_not_called()

    # Test non-numeric input
    with (
        patch.object(Prompt, "ask", return_value="abc"),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])
        assert result is False
        mock_delete.assert_not_called()


def test_handle_delete_empty_input_with_keeper(tmp_path: Path) -> None:
    """Test that empty input uses keeper-based selection."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Set file2 as newer
    current_time = time.time()
    os.utime(file1, (current_time - 100, current_time - 100))
    os.utime(file2, (current_time, current_time))

    with (
        patch.object(Prompt, "ask", return_value=""),  # Empty input
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 1
        assert files_to_delete[0] == file1  # Older file should be deleted
