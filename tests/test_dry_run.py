"""Tests for dry run functionality."""

from pathlib import Path
from typing import Any, Callable, List
from unittest.mock import patch

from rich.console import Console
from rich.prompt import Prompt

from ndetect.cli import process_group
from ndetect.models import MoveConfig, RetentionConfig, TextFile
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action, SimilarGroup
from ndetect.ui import InteractiveUI


def test_dry_run_file_selection(
    configurable_ui: InteractiveUI, create_test_files: List[Path]
) -> None:
    """Test that dry run mode works correctly."""
    file1, file2 = create_test_files[:2]  # Get first two test files

    # Set dry run mode
    configurable_ui.move_config.dry_run = True

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = configurable_ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_process_group_continuation(
    tmp_path: Path, create_file_with_content: Callable[[str, str], Path]
) -> None:
    """Test that process_group continues correctly in dry run mode."""
    file1 = create_file_with_content("test1.txt", "identical content")
    file2 = create_file_with_content("test2.txt", "identical content")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    graph = SimilarityGraph(threshold=0.8)
    graph.add_files(text_files)
    groups = graph.get_groups()
    assert len(groups) > 0, "No groups formed - files not similar enough"
    group = groups[0]

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    with (
        patch.object(Prompt, "ask", return_value="n"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(ui, "prompt_for_action", side_effect=[Action.DELETE, Action.NEXT]),
    ):
        action = process_group(ui, graph, group)
        assert action == Action.NEXT


def test_dry_run_keeper_selection(
    configurable_ui: InteractiveUI, create_file_with_content: Callable[[str, str], Path]
) -> None:
    """Test that dry run mode works correctly with keeper selection."""
    file1 = create_file_with_content("test1.txt", "content1")
    file2 = create_file_with_content("test2.txt", "content2")

    # Set dry run mode
    configurable_ui.move_config.dry_run = True

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = configurable_ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_keeper_override(
    tmp_path: Path,
    configurable_ui: InteractiveUI,
    create_file_with_content: Callable[[str, str], Path],
    mock_prompt_responses: Callable[[dict[str, Any]], Callable[..., Any]],
) -> None:
    """Test that dry run mode works correctly when overriding keeper selection."""
    # Create test files
    file1 = create_file_with_content("test1.txt", "content1")
    file2 = create_file_with_content("test2.txt", "content2")

    # Configure UI for dry run mode
    configurable_ui.move_config.dry_run = True

    # Set up mock responses
    responses = {
        "Select keeper file number": "2",
        "Do you want to select a different keeper?": "y",
        "Are you sure?": True,
    }
    mock_ask = mock_prompt_responses(responses)

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        # In dry run mode, handle_delete should return False
        result = configurable_ui.handle_delete([file1, file2])

        # Verify dry run behavior
        assert result is False  # Should be False in dry run mode
        mock_delete.assert_not_called()  # No actual deletion in dry run
        assert file1.exists()  # Files should still exist
        assert file2.exists()


def test_dry_run_keeper_selection_move_operation(tmp_path: Path) -> None:
    """Test that dry run mode works with keeper selection in move operations."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    group = ui._create_group_from_files([file1, file2])

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
    ):
        result = ui.handle_move(group)

        assert result is False
        mock_execute.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_move_operation(tmp_path: Path) -> None:
    """Test that move operations work correctly in dry run mode."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Create a group
    group = SimilarGroup(
        id=1,
        files=[file1, file2],
        similarity=1.0,
    )

    with (
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
        patch.object(Prompt, "ask", return_value="n"),  # Don't select different keeper
    ):
        result = ui.handle_move(group)

        assert result is False  # Should return False in dry run mode
        mock_execute.assert_not_called()  # Should not execute moves in dry run mode
