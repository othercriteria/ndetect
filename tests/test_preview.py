from pathlib import Path
from typing import Callable
from unittest.mock import Mock, patch

from rich.console import Console

from ndetect.cli import process_group
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig, TextFile
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action
from ndetect.ui import InteractiveUI


def test_preview_action_available(test_console_no_color: Console) -> None:
    """Test that preview action is available in prompt choices."""
    ui = InteractiveUI(
        console=test_console_no_color,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
    )

    with patch.object(Console, "print"):  # Suppress output
        with patch("rich.prompt.Prompt.ask", return_value="p"):
            action = ui.prompt_for_action()
            assert action == Action.PREVIEW


def test_preview_content_display(
    tmp_path: Path,
    configurable_ui: InteractiveUI,
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test that file preview displays correct content."""
    test_file = create_file_with_content(
        "test.txt", "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    )

    with configurable_ui.console.capture() as capture:
        configurable_ui.show_preview([test_file])

    output = capture.get()
    assert "Line 1" in output
    assert "Line 2" in output
    assert "Line 3" not in output
    assert "..." in output


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

    # Just test preview -> next
    mock_prompt = Mock(side_effect=[Action.PREVIEW, Action.NEXT])
    ui.prompt_for_action = mock_prompt  # type: ignore

    action = process_group(ui, graph, groups[0])

    assert mock_prompt.call_count == 2
    assert action == Action.NEXT


def test_preview_generation(
    create_text_file: Callable[[str, str], TextFile],
    configurable_ui: InteractiveUI,
) -> None:
    """Test preview generation with different configurations."""
    test_content = "line1\nline2\nline3\nline4\nline5"
    file = create_text_file("test.txt", test_content)

    test_cases = [
        (PreviewConfig(max_chars=10, max_lines=2), ["line1"]),
        (PreviewConfig(max_chars=100, max_lines=2), ["line1", "line2..."]),
        (PreviewConfig(max_chars=5, max_lines=5), ["li"]),
        (
            PreviewConfig(max_chars=100, max_lines=5),
            ["line1", "line2", "line3", "line4", "line5"],
        ),
        (PreviewConfig(max_chars=100, max_lines=1), ["line1..."]),
    ]

    for config, expected_pieces in test_cases:
        configurable_ui.preview_config = config
        with configurable_ui.console.capture() as capture:
            configurable_ui.show_preview([file.path])
        output = capture.get()
        for piece in expected_pieces:
            assert piece in output, f"Expected '{piece}' in output: {output}"
