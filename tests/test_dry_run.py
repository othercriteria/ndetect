"""Tests for dry run functionality."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from rich.console import Console
from rich.prompt import Prompt

from ndetect.cli import process_group
from ndetect.models import MoveConfig, RetentionConfig, TextFile
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action, SimilarGroup
from ndetect.ui import InteractiveUI


def test_dry_run_file_selection(tmp_path: Path) -> None:
    """Test that dry run correctly identifies files for deletion."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(record=True, width=200)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Mock keeper selection to always return file1
    with patch("ndetect.ui.select_keeper", return_value=file1):
        # Mock user inputs to simulate:
        # 1. Select files to delete ('2')  # Select the non-keeper file
        # 2. Confirm deletion ('y')
        with (
            patch.object(Prompt, "ask", side_effect=["2", "y"]),
            patch("ndetect.ui.Confirm.ask", return_value=True),
            patch("ndetect.ui.delete_files") as mock_delete,
        ):
            result = ui.handle_delete([file1, file2])

        # Verify dry run message shows correct file
        assert result is True
        mock_delete.assert_not_called()
        output = console.export_text()
        assert "Would delete these files" in output
        # Use in operator on normalized paths to handle line wrapping
        assert str(file2).replace("\\", "/") in output.replace("\\", "/")


def test_dry_run_process_group_continuation(tmp_path: Path) -> None:
    """Test that process_group continues after dry run operation."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(record=True, width=200)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Create a similar group
    group = SimilarGroup(id=1, files=[file1, file2], similarity=0.9)
    graph = SimilarityGraph(threshold=0.8)
    graph.add_files([TextFile.from_path(f) for f in [file1, file2]])

    # Mock keeper selection to always return file1
    with patch("ndetect.ui.select_keeper", return_value=file1):
        # Create mock sequences for different prompts
        action_responses = ["d", "q"]
        confirm_responses = [
            False,
            True,
        ]  # First False for keeper override, then True for confirmation
        selection_responses = ["2"]

        def mock_prompt(*args: Any, **kwargs: Any) -> str:
            prompt = str(kwargs.get("prompt", ""))
            if "keeper" in prompt.lower():
                return selection_responses.pop(0)
            return action_responses.pop(0)

        with (
            patch.object(Prompt, "ask", side_effect=mock_prompt),
            patch("ndetect.ui.Confirm.ask", side_effect=confirm_responses),
            patch("ndetect.ui.delete_files"),
        ):
            action = process_group(ui, graph, group)

        assert action == Action.QUIT


def test_dry_run_keeper_selection(tmp_path: Path) -> None:
    """Test that dry run mode works correctly with keeper selection."""
    # Create test files
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

    # Mock keeper selection to always return file1
    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),  # Empty input to use default
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is True
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_keeper_override(tmp_path: Path) -> None:
    """Test that dry run mode works correctly when overriding keeper selection."""
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

    # Simulate user overriding keeper selection
    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(
            Prompt, "ask", side_effect=["y", "2"]
        ),  # Override and select file2
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is True
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_keeper_selection_move_operation(tmp_path: Path) -> None:
    """Test dry run with keeper selection in move operations."""
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

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
    ):
        result = ui.handle_move([file1, file2])

        assert result is True
        mock_execute.assert_not_called()
        assert file1.exists()
        assert file2.exists()
