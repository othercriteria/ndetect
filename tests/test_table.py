"""Tests for table display functionality."""

import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.text import Text

from ndetect.models import MoveConfig, RetentionConfig
from ndetect.types import SimilarGroup
from ndetect.ui import InteractiveUI


def test_keeper_selection_table_display(tmp_path: Path) -> None:
    """Test that keeper selection table displays correct columns and formatting."""
    # Create test files with different timestamps
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"

    current_time = time.time()
    file1.write_text("content1")
    file2.write_text("content2" * 100)  # Make file2 larger

    # Set different timestamps
    os.utime(file1, (current_time - 100, current_time - 100))
    os.utime(file2, (current_time, current_time))

    # Use a very wide console to prevent truncation
    console = Console(force_terminal=True, width=200)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Capture the table output
    with console.capture() as capture:
        ui._display_keeper_selection_table([file1, file2])

    output = Text.from_ansi(capture.get()).plain

    # Check for the presence of filenames (which should be unique enough)
    assert "file1.txt" in output
    assert "file2.txt" in output
    assert "bytes" in output

    # Verify date formatting matches expected pattern
    date_str = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d")
    assert date_str in output


def test_keeper_selection_table_with_error_handling(tmp_path: Path) -> None:
    """Test that keeper selection table handles file stat errors gracefully."""
    # Create one real file and one that will cause an error
    real_file = tmp_path / "real.txt"
    real_file.write_text("content")

    nonexistent_file = tmp_path / "nonexistent.txt"

    # Use a very wide console to prevent truncation
    console = Console(force_terminal=True, width=200)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with console.capture() as capture:
        ui._display_keeper_selection_table([real_file, nonexistent_file])

    output = Text.from_ansi(capture.get()).plain

    # Check for the presence of filenames and error indicators
    assert "real.txt" in output
    assert "nonexistent.txt" in output
    assert "ERROR" in output


def test_keeper_selection_input_handling(tmp_path: Path) -> None:
    """Test keeper selection input handling with various inputs."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    group = SimilarGroup(id=1, files=[file1, file2], similarity=0.8)

    # Test valid input
    with patch("rich.prompt.Prompt.ask", return_value="1"):
        result = ui._handle_keeper_selection(group)
        assert result == file1

    # Test invalid number
    with patch("rich.prompt.Prompt.ask", return_value="3"):
        result = ui._handle_keeper_selection(group)
        assert result is None

    # Test non-numeric input
    with patch("rich.prompt.Prompt.ask", return_value="invalid"):
        result = ui._handle_keeper_selection(group)
        assert result is None


def test_keeper_selection_table_column_alignment(tmp_path: Path) -> None:
    """Test that keeper selection table columns are properly aligned."""
    # Create files with varying name lengths and sizes
    files = [
        (tmp_path / "short.txt", "small"),
        (tmp_path / "medium_name_file.txt", "medium" * 100),
        (tmp_path / "very_long_filename_for_testing.txt", "large" * 1000),
    ]

    for path, content in files:
        path.write_text(content)

    console = Console(force_terminal=True, width=100)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with console.capture() as capture:
        ui._display_keeper_selection_table([p for p, _ in files])

    output = Text.from_ansi(capture.get()).plain
    lines = output.splitlines()

    # Find lines containing numbers and verify alignment
    number_lines = [line for line in lines if any(str(n) in line for n in range(1, 4))]
    number_positions = [line.find(str(i)) for i, line in enumerate(number_lines, 1)]

    # Verify numbers are consistently positioned
    assert len(set(number_positions)) == 1, "Numbers should be aligned"

    # Verify size column alignment
    size_lines = [line for line in lines if "bytes" in line]
    size_positions = [line.find("bytes") for line in size_lines]
    assert len(set(size_positions)) == 1, "Sizes should be aligned"
