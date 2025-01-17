import os
import time
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import MoveOperation
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

    # Mock both confirm and delete_files
    with (
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        ui.handle_delete([file1, file2, file3])
        # file3 should be kept as it's the newest
        mock_delete.assert_called_once_with([file1, file2])


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

    # Setup UI with retention_config and move_config
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Mock confirm, prepare_moves, and execute_moves
    with (
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.prepare_moves") as mock_prepare,
        patch("ndetect.ui.execute_moves") as mock_execute,
    ):
        # Setup mock prepare_moves to return a list of mock moves
        mock_moves = [
            MoveOperation(file1, move_config.holding_dir / "file1.txt", 1),
            MoveOperation(file2, move_config.holding_dir / "file2.txt", 1),
        ]
        mock_prepare.return_value = mock_moves

        # Execute the move operation
        ui.handle_move([file1, file2, file3])

        # Verify prepare_moves was called with correct parameters
        mock_prepare.assert_called_once_with(
            files=[file1, file2],  # file3 should be kept
            holding_dir=move_config.holding_dir,
            preserve_structure=move_config.preserve_structure,
        )

        # Verify execute_moves was called with the mock moves
        mock_execute.assert_called_once_with(mock_moves)
