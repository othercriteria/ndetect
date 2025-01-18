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
        # Create two separate mock sequences:
        # 1. For action prompts: delete then quit
        # 2. For file selection: select file 2
        action_responses = ["d", "q"]
        selection_responses = ["2", "y"]

        def mock_prompt(*args: Any, **kwargs: Any) -> str:
            if "Select files" in str(kwargs.get("prompt", "")):
                return selection_responses.pop(0)
            return action_responses.pop(0)

        with (
            patch.object(Prompt, "ask", side_effect=mock_prompt),
            patch("ndetect.ui.Confirm.ask", return_value=True),
            patch("ndetect.ui.delete_files"),
        ):
            action = process_group(ui, graph, group)

        # Verify we reached the quit action
        assert action == Action.QUIT
        # Verify the dry run operation was shown
        output = console.export_text()
        assert "Would delete these files" in output
        assert str(file2).replace("\\", "/") in output.replace("\\", "/")


def test_dry_run_process_group_loop(tmp_path: Path) -> None:
    """Test that process_group continues looping after dry run operation."""
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

    # Track the sequence of actions processed
    processed_actions = []

    # Mock keeper selection to always return file1
    with patch("ndetect.ui.select_keeper", return_value=file1):
        # Create two separate mock sequences:
        # 1. For action prompts: delete then quit
        # 2. For file selection: select file 2
        action_responses = ["d", "q"]
        selection_responses = ["2", "y"]

        def mock_prompt(*args: Any, **kwargs: Any) -> str:
            if "Select files" in str(kwargs.get("prompt", "")):
                return selection_responses.pop(0)
            action = action_responses.pop(0)
            if action == "d":
                processed_actions.append(Action.DELETE)
            elif action == "q":
                processed_actions.append(Action.QUIT)
            return action

        with (
            patch.object(Prompt, "ask", side_effect=mock_prompt),
            patch("ndetect.ui.Confirm.ask", return_value=True),
            patch("ndetect.ui.delete_files"),
        ):
            action = process_group(ui, graph, group)

        # Verify we processed both DELETE and QUIT actions
        assert Action.DELETE in processed_actions
        assert Action.QUIT in processed_actions
        assert processed_actions[-1] == Action.QUIT
        # Verify the final returned action is QUIT
        assert action == Action.QUIT


def test_dry_run_process_group(tmp_path: Path) -> None:
    """Test that dry run correctly identifies files for deletion in process_group."""
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
        # Create two separate mock sequences:
        # 1. For action prompts: delete then quit
        # 2. For file selection: select file 2
        action_responses = ["d", "q"]
        selection_responses = ["2", "y"]

        def mock_prompt(*args: Any, **kwargs: Any) -> str:
            if "Select files" in str(kwargs.get("prompt", "")):
                return selection_responses.pop(0)
            return action_responses.pop(0)

        with (
            patch.object(Prompt, "ask", side_effect=mock_prompt),
            patch("ndetect.ui.Confirm.ask", return_value=True),
            patch("ndetect.ui.delete_files"),
        ):
            action = process_group(ui, graph, group)

        # Verify we reached the quit action
        assert action == Action.QUIT
        # Verify the dry run operation was shown
        output = console.export_text()
        assert "Would delete these files" in output
        assert str(file2).replace("\\", "/") in output.replace("\\", "/")
