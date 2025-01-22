"""Tests for dry run functionality."""

from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

from rich.console import Console
from rich.prompt import Prompt

from ndetect.cli import process_group
from ndetect.models import MoveConfig, RetentionConfig, TextFile
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action
from ndetect.ui import InteractiveUI


def test_dry_run_file_selection(tmp_path: Path) -> None:
    """Test that dry run mode works correctly with file selection."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_dry_run_process_group_continuation(tmp_path: Path) -> None:
    """Test that process_group continues correctly in dry run mode."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    # Make files identical to ensure they form a group
    file1.write_text("identical content")
    file2.write_text("identical content")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),  # Enable minhash computation
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

    # Mock all prompts and confirmations
    with (
        patch.object(Prompt, "ask", return_value="n"),  # Don't override keeper
        patch("ndetect.ui.Confirm.ask", return_value=True),  # Confirm all actions
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(ui, "prompt_for_action", side_effect=[Action.DELETE, Action.NEXT]),
    ):
        action = process_group(ui, graph, group)
        assert action == Action.NEXT


def test_dry_run_keeper_selection(tmp_path: Path) -> None:
    """Test that dry run mode works correctly with keeper selection."""
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
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is False
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

    def mock_ask(prompt: str, choices: Optional[List[str]] = None) -> str:
        if "Select keeper file number" in str(prompt):
            assert choices == ["1", "2"], f"Expected choices [1,2], got {choices}"
            return "2"
        if "Do you want to select a different keeper?" in str(prompt):
            return "y"
        return ""

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()
        assert file1.exists()
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

    with (
        patch("ndetect.ui.select_keeper", return_value=file1),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
    ):
        result = ui.handle_move([file1, file2])

        assert result is False
        mock_execute.assert_not_called()
        assert file1.exists()
        assert file2.exists()
