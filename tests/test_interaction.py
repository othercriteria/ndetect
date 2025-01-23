"""Test interactive delete functionality with retention config."""

import os
import time
from pathlib import Path
from typing import Any, Callable, List, Optional
from unittest.mock import patch

from rich.console import Console
from rich.prompt import Prompt

from ndetect.models import MoveConfig, RetentionConfig
from ndetect.operations import MoveOperation
from ndetect.ui import InteractiveUI


def test_handle_delete_with_retention_config(
    configurable_ui: InteractiveUI,
    create_file_with_content: Callable[[str, str], Path],
    mock_prompt_responses: Callable[[dict[str, Any]], Callable[..., Any]],
) -> None:
    """Test delete handling with retention config."""
    file1 = create_file_with_content("small.txt", "small")
    file2 = create_file_with_content("large.txt", "large content" * 100)

    configurable_ui.retention_config.strategy = "largest"

    responses = {
        "Do you want to select a different keeper?": False,
        "Are you sure you want to delete these files?": True,
    }
    mock_ask = mock_prompt_responses(responses)

    with (
        patch("ndetect.ui.Confirm.ask", side_effect=mock_ask),
        patch("ndetect.ui.delete_files") as mock_delete,
        patch.object(Prompt, "ask", return_value=""),
    ):
        result = configurable_ui.handle_delete([file1, file2])
        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 1
        assert files_to_delete[0] == file1  # Should delete smaller file


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
        patch(
            "ndetect.ui.Confirm.ask", return_value=False
        ),  # Mock Confirm.ask to return False
        patch.object(Prompt, "ask", return_value=""),  # Mock Prompt.ask if used
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

    def mock_confirm(*args: Any, **kwargs: Any) -> bool:
        msg = str(args[0] if args else kwargs.get("prompt", ""))
        if "Do you want to select a different keeper?" in msg:
            return False
        return True

    with (
        patch("ndetect.ui.Confirm.ask", side_effect=mock_confirm),
        patch("ndetect.ui.delete_files") as mock_delete,
        patch.object(Prompt, "ask", return_value=""),  # Empty response for any prompts
    ):
        result = ui.handle_delete([priority_file, other_file])
        assert result is True
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 1
        assert files_to_delete[0] == other_file  # Should delete non-priority file


def test_handle_delete_invalid_selection(tmp_path: Path) -> None:
    """Test delete handling with invalid user selection."""
    file1 = tmp_path / "invalid.txt"
    file1.write_text("invalid content")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch(
            "ndetect.ui.Confirm.ask", return_value=False
        ),  # User chooses not to override
        patch.object(
            Prompt, "ask", return_value="invalid_option"
        ),  # Mock invalid input if prompted
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1])

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


def test_handle_move_keeper_override(tmp_path: Path) -> None:
    """Test that keeper selection can be overridden by user in move operations."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    file3.write_text("content3")

    # Set file3 as the default keeper
    current_time = time.time()
    os.utime(file1, (current_time - 200, current_time - 200))
    os.utime(file2, (current_time - 100, current_time - 100))
    os.utime(file3, (current_time, current_time))

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Track which prompt is being answered
    prompt_count = 0

    def mock_ask(prompt: str, choices: Optional[List[str]] = None) -> str:
        nonlocal prompt_count
        prompt_count += 1

        # First prompt: "Do you want to select a different keeper?"
        if prompt_count == 1:
            return "y"
        # Second prompt: "Select keeper file number"
        elif prompt_count == 2:
            assert choices == [
                "1",
                "2",
                "3",
            ], f"Expected choices [1,2,3], got {choices}"
            return "2"
        return ""

    with (
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
        patch(
            "ndetect.ui.prepare_moves",
            return_value=[
                MoveOperation(
                    source=file1,
                    destination=move_config.holding_dir / "file1.txt",
                    group_id=1,
                ),
                MoveOperation(
                    source=file3,
                    destination=move_config.holding_dir / "file3.txt",
                    group_id=1,
                ),
            ],
        ),
    ):
        result = ui.handle_move([file1, file2, file3])

        assert result is True
        mock_execute.assert_called_once()
        moves = mock_execute.call_args[0][0]

        # Verify that file1 and file3 are moved, and file2 is kept
        moved_files = {move.source for move in moves}
        assert file1 in moved_files, "file1 should be moved"
        assert file3 in moved_files, "file3 should be moved"
        assert file2 not in moved_files, "file2 should be kept as the new keeper"

        # Add debug assertions
        print("\nDebug - Prompt responses:")
        print(f"  Total prompts: {prompt_count}")
        print(f"  Moved files: {moved_files}")
