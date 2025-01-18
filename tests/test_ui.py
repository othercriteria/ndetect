import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

import pytest
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import MoveOperation
from ndetect.types import Action
from ndetect.ui import InteractiveUI


def test_show_preview_respects_limits(tmp_path: Path) -> None:
    """Test that show_preview respects character and line limits."""
    # Create test file with multiple lines
    test_file = tmp_path / "test.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

    console = Console(force_terminal=True)
    # Use larger limits to ensure we see both lines
    preview_config = PreviewConfig(max_chars=20, max_lines=2)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        preview_config=preview_config,
    )

    # Capture output
    with console.capture() as capture:
        ui.show_preview([test_file])

    output = capture.get()
    # Should show both lines since we have enough space
    assert "Line 1" in output
    assert "Line 2" in output
    assert "Line 3" not in output


def test_show_similarities(tmp_path: Path) -> None:
    """Test that show_similarities displays correct pairwise similarities."""
    # Create console with very wide width to prevent truncation
    console = Console(force_terminal=True, width=200)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
    )

    # Create test files with shorter paths
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file3 = tmp_path / "test3.txt"

    files = [file1, file2, file3]
    similarities = {
        (file1, file2): 0.85,
        (file1, file3): 0.75,
        (file2, file3): 0.95,
    }

    # Get the table directly
    table = ui.format_similarity_table(files, similarities)

    # Test table structure
    assert isinstance(table, Table)
    assert len(table.columns) == 3
    assert table.columns[0].header == "File 1"
    assert table.columns[1].header == "File 2"
    assert table.columns[2].header == "Similarity"

    # Verify table width
    assert table.width == 200

    # Get rendered content for verification
    with console.capture() as capture:
        console.print(table)
    output = capture.get()

    # Convert to plain text (removes ANSI codes)
    plain_text = Text.from_ansi(output).plain
    output_lines = plain_text.splitlines()

    # Get data rows (skip header and border rows)
    data_rows = [line for line in output_lines if "│" in line and "%" in line]

    # Verify we have the expected number of data rows
    assert len(data_rows) == len(similarities)

    # Verify all filenames appear in the output
    file_patterns = {"test1.txt", "test2.txt", "test3.txt"}
    found_patterns = set()
    for row in data_rows:
        for pattern in file_patterns:
            if pattern in row:
                found_patterns.add(pattern)
    assert found_patterns == file_patterns

    # Verify all percentages appear
    percentages = {"85.00%", "75.00%", "95.00%"}
    found_percentages = set()
    for row in data_rows:
        for percentage in percentages:
            if percentage in row:
                found_percentages.add(percentage)
    assert found_percentages == percentages


def test_handle_delete_with_select_keeper(tmp_path: Path) -> None:
    """Test handle_delete using select_keeper to retain one file and delete others."""
    # Create test files
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    file3.write_text("content3")

    # Configure retention strategy
    retention_config = RetentionConfig(strategy="newest")

    # Modify file timestamps to make file3 the newest
    current_time = time.time()
    os.utime(file1, (current_time - 300, current_time - 300))  # 5 minutes ago
    os.utime(file2, (current_time - 200, current_time - 200))  # ~3 minutes ago
    os.utime(file3, (current_time - 100, current_time - 100))  # ~1.5 minutes ago

    # Setup UI with retention_config
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Mock Prompt.ask, Confirm.ask, and delete_files
    with (
        patch.object(Prompt, "ask", return_value="1,2"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        ui.handle_delete([file1, file2, file3])

        # Verify that file1 and file2 were deleted (file3 is newest)
        mock_delete.assert_called_once()
        files_to_delete = mock_delete.call_args[0][0]
        assert len(files_to_delete) == 2
        assert file1 in files_to_delete
        assert file2 in files_to_delete
        assert file3 not in files_to_delete  # newest file should be kept


def test_handle_move_with_select_keeper(tmp_path: Path) -> None:
    """Test handle_move using select_keeper to retain one file and move others."""
    # Create test files
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    file3.write_text("content3")

    # Configure retention strategy
    retention_config = RetentionConfig(strategy="newest")

    # Modify file timestamps to make file3 the newest
    current_time = time.time()
    os.utime(file1, (current_time - 300, current_time - 300))  # 5 minutes ago
    os.utime(file2, (current_time - 200, current_time - 200))  # ~3 minutes ago
    os.utime(file3, (current_time - 100, current_time - 100))  # ~1.5 minutes ago

    # Setup UI with retention_config
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Create mock move operations
    def mock_prepare_moves(
        files: List[Path],
        holding_dir: Path,
        preserve_structure: bool = True,
        group_id: int = 0,
        base_dir: Optional[Path] = None,
        retention_config: Optional[RetentionConfig] = None,
    ) -> List[MoveOperation]:
        # Don't select keeper here, just prepare moves for all files except file3
        return [
            MoveOperation(
                source=f,
                destination=holding_dir / f.name,
                group_id=group_id,
                timestamp=datetime.now(),
                executed=False,
            )
            for f in files
            if f != file3  # Exclude the newest file
        ]

    def mock_select_keeper(
        files: List[Path], config: RetentionConfig, base_dir: Optional[Path] = None
    ) -> Path:
        return file3  # Always select file3 as keeper

    def mock_execute_moves(moves: List[MoveOperation]) -> None:
        """Mock execute_moves to track the moves without actually moving files."""
        for move in moves:
            mock_move(str(move.source), str(move.destination))
            move.executed = True

    # Mock the necessary components
    with (
        patch.object(
            Prompt, "ask", return_value=""
        ),  # Empty input to use default selection
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.prepare_moves", side_effect=mock_prepare_moves),
        patch("ndetect.ui.select_keeper", side_effect=mock_select_keeper),
        patch("ndetect.ui.execute_moves", side_effect=mock_execute_moves),
        patch(
            "ndetect.operations.shutil.move"
        ) as mock_move,  # Mock shutil.move in operations module
    ):
        result = ui.handle_move([file1, file2, file3])

        assert result is True, "Move operation should succeed"

        # Debug print
        print("\nDebug - Mock move calls:")
        for call in mock_move.call_args_list:
            print(f"  Moving {call.args[0]} to {call.args[1]}")

        # Verify the moves
        assert mock_move.call_count == 2, "Should have moved 2 files"
        moved_files = {Path(call.args[0]) for call in mock_move.call_args_list}
        assert file1 in moved_files, "file1 should be moved"
        assert file2 in moved_files, "file2 should be moved"
        assert file3 not in moved_files, "file3 (newest) should not be moved"


def test_show_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that help information is displayed correctly."""
    # Setup UI
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=Path("holding"))
    ui = InteractiveUI(console=console, move_config=move_config)

    # Mock logger to avoid actual logging
    with patch.object(ui, "logger") as mock_logger:
        ui.show_help()

        # Verify logger was called
        mock_logger.info_with_fields.assert_called_once_with(
            "Displaying help", operation="ui", type="help"
        )

        # Get output and convert to plain text
        output = capsys.readouterr().out
        plain_text = Text.from_ansi(output).plain

        # Verify all actions are shown in help text
        assert "k: Keep all files in this group" in plain_text
        assert "d: Delete selected files" in plain_text
        assert "m: Move selected files to holding directory" in plain_text
        assert "p: Preview file contents" in plain_text
        assert "s: Show similarities between files" in plain_text
        assert "q: Quit program" in plain_text
        assert "Available Actions" in plain_text


def test_prompt_for_action_help(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that help action is properly handled in prompt."""
    # Setup UI
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=Path("holding"))
    ui = InteractiveUI(console=console, move_config=move_config)

    # Mock Prompt.ask to return 'h'
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: "h")

    # Verify help action is returned
    action = ui.prompt_for_action()
    assert action == Action.HELP
