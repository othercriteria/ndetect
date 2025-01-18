from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from ndetect.cli import process_group
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig, TextFile
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action
from ndetect.ui import InteractiveUI


def test_preview_action_available() -> None:
    """Test that preview action is available in prompt choices."""
    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with patch.object(Console, "print"):  # Suppress output
        with patch("rich.prompt.Prompt.ask", return_value="p"):
            action = ui.prompt_for_action()
            assert action == Action.PREVIEW


def test_preview_content_display(tmp_path: Path) -> None:
    """Test that file preview displays correct content."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
        preview_config=PreviewConfig(max_chars=20, max_lines=2),
    )

    with console.capture() as capture:
        ui.show_preview([test_file])

    output = capture.get()
    assert "Line 1" in output
    assert "Line 2" in output
    assert "Line 3" not in output
    assert "..." in output  # Truncation marker


def test_preview_binary_file(tmp_path: Path) -> None:
    """Test preview handling of binary files."""
    # Create binary file
    binary_file = tmp_path / "test.bin"
    binary_file.write_bytes(bytes([0x00, 0x01, 0x02, 0x03]))

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with console.capture() as capture:
        ui.show_preview([binary_file])

    output = capture.get()
    assert "binary" in output.lower() or "unsupported encoding" in output.lower()


def test_preview_nonexistent_file(tmp_path: Path) -> None:
    """Test preview handling of nonexistent files."""
    nonexistent = tmp_path / "nonexistent.txt"

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with console.capture() as capture:
        ui.show_preview([nonexistent])

    output = capture.get()
    assert "not found" in output.lower()


def test_preview_empty_file_list() -> None:
    """Test preview handling of empty file list."""
    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with console.capture() as capture:
        ui.show_preview([])

    output = capture.get()
    assert "no files to preview" in output.lower()


def test_preview_with_custom_config(tmp_path: Path) -> None:
    """Test preview with custom configuration."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test file with some content")

    console = Console(force_terminal=True, width=80)
    config = PreviewConfig(max_lines=5, max_chars=100)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
        preview_config=config,
    )

    # Capture the output
    with console.capture() as capture:
        ui.show_preview([test_file])

    output = capture.get()
    # Check for content without ANSI escape codes
    from rich.text import Text

    plain_output = Text.from_ansi(output).plain
    assert "This is" in plain_output


def test_process_group_preview_continues(tmp_path: Path) -> None:
    """Test that preview action allows continuing with the same group."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("hello world")
    file2.write_text("hello world")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    graph = SimilarityGraph(threshold=0.5)
    graph.add_files(text_files)
    groups = graph.get_groups()

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Mock sequence: preview -> similarities -> next
    mock_prompt = Mock(side_effect=[Action.PREVIEW, Action.SIMILARITIES, Action.NEXT])
    ui.prompt_for_action = mock_prompt  # type: ignore

    # Run the process
    action = process_group(ui, graph, groups[0])

    # Verify all actions were called
    assert mock_prompt.call_count == 3
    assert action == Action.NEXT  # Final action should be next
