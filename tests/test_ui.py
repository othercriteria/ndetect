from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ndetect.models import MoveConfig, PreviewConfig
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
