import logging
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any, Callable, List, Optional
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from ndetect.logging import get_logger
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import select_keeper
from ndetect.types import Action, SimilarGroup
from ndetect.ui import InteractiveUI


def test_show_preview_respects_limits(
    tmp_path: Path,
    configurable_ui: InteractiveUI,
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test that preview respects max lines and chars limits."""
    # Create a real file that exists on disk
    test_file = create_file_with_content(
        "test.txt", "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    )

    with configurable_ui.console.capture() as capture:
        configurable_ui.show_preview([test_file])

    output = capture.get()
    assert "Line 1" in output
    assert "Line 2" in output
    assert "Line 3" not in output  # Should be truncated due to max_lines=2


def test_show_similarities(tmp_path: Path) -> None:
    """Test that show_similarities displays correct pairwise similarities."""
    # Create console with very wide width to prevent truncation
    console = Console(force_terminal=True, width=200)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
        retention_config=RetentionConfig(strategy="newest"),
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

    # Verify table width matches console width
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

    # Verify all filenames appear in the output (accounting for truncation)
    file_patterns = {
        "test1",
        "test2",
        "test3",
    }  # Remove .txt since it might be truncated
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


def test_show_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that help information is displayed correctly."""
    # Setup UI
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=Path("holding"))
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

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
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Mock Prompt.ask to return 'h'
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: "h")

    # Verify help action is returned
    action = ui.prompt_for_action()
    assert action == Action.HELP


def test_unified_keeper_selection_behavior(tmp_path: Path) -> None:
    """Test that keeper selection behavior is consistent between move and delete."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    group = ui._create_group_from_files([file1, file2])

    with (
        patch.object(Prompt, "ask", return_value="n"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves"),
    ):
        result_move = ui.handle_move(group)
        assert result_move is True


def test_keeper_selection_happens_once(tmp_path: Path) -> None:
    """Test that keeper selection only happens once during file operation."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    mock_select_keeper = Mock(return_value=file1)

    with (
        patch("ndetect.ui.select_keeper", mock_select_keeper),
        patch("ndetect.ui.Confirm.ask", return_value=False),  # Don't override keeper
        patch("ndetect.ui.delete_files"),
    ):
        ui.handle_delete([file1, file2])

        mock_select_keeper.assert_called_once()


def test_empty_input_uses_default_selection(tmp_path: Path) -> None:
    """Test that pressing Enter uses the default selection (all except keeper)."""
    # Create test files
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    file3.write_text("content3")

    # Make file3 the newest (keeper)
    current_time = time.time()
    os.utime(file1, (current_time - 300, current_time - 300))
    os.utime(file2, (current_time - 200, current_time - 200))
    os.utime(file3, (current_time - 100, current_time - 100))

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    # Track what files are actually processed
    processed_files = []

    def mock_delete(files: List[Path]) -> None:
        processed_files.extend(files)

    with (
        patch.object(Prompt, "ask", return_value=""),  # User presses Enter
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files", side_effect=mock_delete),
    ):
        result = ui.handle_delete([file1, file2, file3])

        assert result is True, "Operation should succeed with default selection"
        assert (
            len(processed_files) == 2
        ), f"Expected 2 files to be processed, got {len(processed_files)}"
        assert file1 in processed_files, "Older file1 should be selected"
        assert file2 in processed_files, "Older file2 should be selected"
        assert (
            file3 not in processed_files
        ), "Newest file (keeper) should not be selected"


def test_logger_configuration(tmp_path: Path) -> None:
    """Test that logger is configured correctly with no duplicate handlers."""
    import logging
    import sys

    from ndetect.logging import get_logger, setup_logging

    # First clear any existing handlers
    logger = get_logger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set up logging fresh
    log_file = tmp_path / "test.log"
    setup_logging(log_file)

    # Get all handlers
    handlers = logger.handlers

    # Categorize handlers
    stream_handlers = [
        h
        for h in handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
    ]
    file_handlers = [h for h in handlers if isinstance(h, logging.FileHandler)]

    # Print debug info
    print("\nLogger configuration:")
    print(f"Total handlers: {len(handlers)}")
    for h in handlers:
        print(f"Handler: {h}, type: {type(h)}, stream: {getattr(h, 'stream', None)}")

    # Verify handler counts
    assert len(stream_handlers) == 1, (
        f"Should have exactly one StreamHandler, got {len(stream_handlers)}:\n"
        + "\n".join(f"  {h}" for h in stream_handlers)
    )
    assert len(file_handlers) == 1, (
        f"Should have exactly one FileHandler, got {len(file_handlers)}:\n"
        + "\n".join(f"  {h}" for h in file_handlers)
    )

    # Verify handler levels and streams
    stream_handler = stream_handlers[0]
    file_handler = file_handlers[0]

    assert (
        file_handler.level == logging.DEBUG
    ), f"File handler should be DEBUG level, got {file_handler.level}"
    assert (
        stream_handler.level == logging.INFO
    ), f"Stream handler should be INFO level, got {stream_handler.level}"

    # Verify stream handler is using stderr
    assert (
        stream_handler.stream == sys.stderr
    ), f"Stream handler should use sys.stderr, got {stream_handler.stream}"

    # Verify log file location
    assert file_handler.baseFilename == str(
        log_file
    ), f"Log file should be at {log_file}, but was at {file_handler.baseFilename}"

    # Test logging at different levels
    test_messages = {
        "debug": "Debug message",
        "info": "Info message",
        "warning": "Warning message",
        "error": "Error message",
    }

    for level, msg in test_messages.items():
        getattr(logger, level)(msg)

    # Verify log file contents
    log_contents = log_file.read_text()
    print("\nLog file contents:")
    print(log_contents)

    # All messages should be in the log file
    for msg in test_messages.values():
        assert msg in log_contents, f"Message '{msg}' not found in log file"


def tracked_select_keeper(*args: Any, **kwargs: Any) -> Path:
    """Track select_keeper calls with their full stack traces."""
    result = select_keeper(*args, **kwargs)
    print(f"\nselect_keeper called with args: {args}")
    print(f"Returning: {result}")
    return result


def test_ui_logging_and_selection_flow(tmp_path: Path, caplog: Any) -> None:
    """Test the UI flow including logging behavior."""
    import ndetect.ui as ui_module
    from ndetect.operations import select_keeper

    # Create test files
    file1 = tmp_path / "dist-info/LICENSE.txt"
    file2 = tmp_path / "site-packages/LICENSE.txt"
    file1.parent.mkdir(parents=True)
    file2.parent.mkdir(parents=True)
    file1.write_text("content1")
    file2.write_text("content2")

    output = StringIO()
    console = Console(file=output, force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")

    def tracked_select_keeper(*args: Any, **kwargs: Any) -> Path:
        result = select_keeper(*args, **kwargs)
        print(f"\nselect_keeper called with args: {args}")
        print(f"Returning: {result}")
        return result

    with (
        patch.object(ui_module, "select_keeper", side_effect=tracked_select_keeper),
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files"),
    ):
        ui = InteractiveUI(
            console=console, move_config=move_config, retention_config=retention_config
        )

        caplog.clear()
        ui.handle_delete([file1, file2])

        # Group log records by message to detect duplicates
        message_sources: dict[str, list[str]] = {}
        for record in caplog.records:
            if record.message not in message_sources:
                message_sources[record.message] = []
            message_sources[record.message].append(f"{record.pathname}:{record.lineno}")


def test_preview_display(tmp_path: Path) -> None:
    """Test file preview display with line and character limits."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content\nline 2\nline 3\nline 4")
    file2.write_text("different content")

    # Use no_color=True and width=100 for consistent output
    console = Console(force_terminal=True, no_color=True, width=100)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
        preview_config=PreviewConfig(max_chars=10, max_lines=2),
    )

    with console.capture() as capture:
        ui.show_preview([file1, file2])

    output = capture.get()
    # Just check for the truncated content
    assert "test co" in output  # First 7 chars of "test content"
    assert "differ" in output  # Start of "different content"


def test_display_group_table_format(tmp_path: Path) -> None:
    """Test that group display shows correct table format with all columns."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content")
    file2.write_text("content")

    console = Console(force_terminal=True, no_color=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    group = SimilarGroup(id=1, files=[file1, file2], similarity=0.85)

    with console.capture() as capture:
        ui.display_group(group)

    output = Text.from_ansi(capture.get()).plain
    assert "85.00% similar" in output
    assert "#" in output
    assert "File" in output
    assert "Size" in output
    assert "Modified" in output


def test_display_files_with_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test display_files handles permission and other OS errors."""
    # Set up logging capture at the root logger level
    caplog.set_level(logging.ERROR)  # Capture all loggers

    file1 = tmp_path / "test1.txt"
    file1.write_text("content")

    file2 = tmp_path / "noperm.txt"
    file2.write_text("content")
    os.chmod(file2, 0o000)

    console = Console(force_terminal=True, no_color=True, width=100)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
        logger=get_logger(),  # Add logger explicitly
    )

    # Clear any existing records
    caplog.clear()

    with console.capture() as capture:
        ui.display_files([file1, file2])

    output = capture.get()
    assert "test1.txt" in output
    assert "noperm.txt" in output

    # Print captured logs for debugging
    print("\nCaptured logs:")
    for record in caplog.records:
        print(f"Level: {record.levelname}, Message: {record.message}")

    # Check for error messages in the console output
    assert any(
        msg in output.lower()
        for msg in ["permission denied", "failed to get file stats", "error"]
    ), f"No error message found in output: {output}"

    # Cleanup
    os.chmod(file2, 0o666)


def test_display_files_error_handling(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test display_files handles stat errors gracefully."""
    # Set up logging capture at the root logger level
    caplog.set_level(logging.ERROR, logger="ndetect")

    file1 = tmp_path / "test1.txt"
    file1.write_text("content")
    non_existent = tmp_path / "nonexistent.txt"

    console = Console(force_terminal=True, no_color=True, width=100)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=tmp_path / "duplicates"),
        retention_config=RetentionConfig(strategy="newest"),
    )

    # Clear any existing records
    caplog.clear()

    with console.capture() as capture:
        ui.display_files([file1, non_existent])

    output = capture.get()
    assert "test1.txt" in output
    assert "nonexistent.t" in output  # Filename might be truncated

    # Print captured logs for debugging
    print("\nCaptured logs:")
    for record in caplog.records:
        print(f"Level: {record.levelname}, Message: {record.message}")

    # Check for any error related to missing file
    error_messages = [
        record.message for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert any(
        "no such file" in msg.lower()
        or "failed to get file stats" in msg.lower()
        or "errno 2" in msg.lower()  # Common "file not found" error code
        for msg in error_messages
    ), f"No file not found error in logs: {error_messages}"


def test_dry_run_delete_operation(tmp_path: Path) -> None:
    """Test that delete_files is not called during dry-run delete operations."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()


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

    group = ui._create_group_from_files([file1, file2])

    with (
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
        patch.object(Prompt, "ask", return_value="n"),  # Don't select different keeper
    ):
        result = ui.handle_move(group)

        assert result is False  # Should return False in dry run mode
        mock_execute.assert_not_called()  # Should not execute moves in dry run mode


def test_dry_run_continues_execution(tmp_path: Path) -> None:
    """Test that execution continues correctly during dry-run."""
    # Setup files and UI
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates", dry_run=True)
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    with (
        patch.object(Prompt, "ask", return_value=""),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        result = ui.handle_delete([file1, file2])

        assert result is False
        mock_delete.assert_not_called()


def test_dry_run_interactive_loop(tmp_path: Path) -> None:
    """Test that dry run mode continues interactive loop after delete operation."""
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

    # Mock user inputs to simulate interactive loop:
    # First return 'd' for delete, then 'q' for quit
    action_responses = iter(["d", "q"])

    def mock_action(*args: Any, **kwargs: Any) -> str:
        return next(action_responses)

    with (
        patch.object(Prompt, "ask", side_effect=mock_action),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.delete_files") as mock_delete,
    ):
        # Create a similar group to process
        group = SimilarGroup(id=1, files=[file1, file2], similarity=0.9)
        group.keeper = file1  # Set keeper file

        # Run the interactive loop
        ui.handle_delete([file1, file2])

        # Verify no actual deletions occurred
        mock_delete.assert_not_called()
        assert file1.exists()
        assert file2.exists()


def test_move_operation_keeper_consistency(tmp_path: Path) -> None:
    """Test that move operations maintain the same keeper throughout the operation."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    # Set different timestamps
    current_time = time.time()
    os.utime(file1, (current_time - 100, current_time - 100))
    os.utime(file2, (current_time, current_time))  # file2 is newer

    console = Console(force_terminal=True)
    retention_config = RetentionConfig(strategy="newest")
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console, move_config=move_config, retention_config=retention_config
    )

    group = ui._create_group_from_files([file1, file2])

    with (
        patch.object(Prompt, "ask", return_value="n"),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves") as mock_execute,
    ):
        result = ui.handle_move(group)
        assert result is True
        mock_execute.assert_called_once()
        moves = mock_execute.call_args[0][0]
        moved_files = {move.source for move in moves}
        assert len(moved_files) == 1, "Should only move one file"
        assert file1 in moved_files, "Should move older file"
        assert file2 not in moved_files, "Should not move keeper (newer file)"


def test_handle_move_keeper_override(tmp_path: Path) -> None:
    """Test that keeper selection can be overridden by user in move operations."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file3 = tmp_path / "file3.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    file3.write_text("content3")

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="newest"),
    )

    group = ui._create_group_from_files([file1, file2, file3])

    def mock_ask(prompt: str, choices: Optional[List[str]] = None) -> str:
        if "Select keeper file number" in str(prompt):
            return "2"  # Select file2 as keeper
        if "Do you want to select a different keeper?" in str(prompt):
            return "y"
        return ""

    with (
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves"),
    ):
        result = ui.handle_move(group)
        assert result is True


def test_preview_empty_file_list(configurable_ui: InteractiveUI) -> None:
    """Test preview handling of empty file list."""
    with configurable_ui.console.capture() as capture:
        configurable_ui.show_preview([])

    output = capture.get()
    assert "No files to preview" in output


def test_handle_move_respects_keeper_across_groups(tmp_path: Path) -> None:
    """Test that handle_move respects keeper selection across multiple groups."""
    files = [
        (tmp_path / "file1.txt", "small"),
        (tmp_path / "file2.txt", "medium" * 10),
        (tmp_path / "file3.txt", "large" * 100),
    ]
    for path, content in files:
        path.write_text(content)

    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=tmp_path / "duplicates")
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        retention_config=RetentionConfig(strategy="largest"),
    )

    group = ui._create_group_from_files([p for p, _ in files])

    def mock_ask(prompt: str, choices: Optional[List[str]] = None) -> str:
        if "Select keeper file number" in str(prompt):
            return "2"  # Select file2 as keeper
        if "Do you want to select a different keeper?" in str(prompt):
            return "y"
        return ""

    with (
        patch.object(Prompt, "ask", side_effect=mock_ask),
        patch("ndetect.ui.Confirm.ask", return_value=True),
        patch("ndetect.ui.execute_moves"),
    ):
        result = ui.handle_move(group)
        assert result is True
