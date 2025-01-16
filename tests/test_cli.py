from pathlib import Path
from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from ndetect.cli import (
    handle_non_interactive_mode,
    parse_args,
    process_group,
    scan_paths,
)
from ndetect.exceptions import FileOperationError
from ndetect.models import MoveConfig, RetentionConfig, TextFile
from ndetect.operations import execute_moves, prepare_moves
from ndetect.similarity import SimilarityGraph
from ndetect.types import Action
from ndetect.ui import InteractiveUI


@pytest.fixture
def cleanup_duplicates() -> Generator[None, None, None]:
    """Clean up the duplicates directory after tests."""
    yield
    duplicates_dir = Path("duplicates")
    if duplicates_dir.exists():
        for file in duplicates_dir.glob("**/*"):
            if file.is_file():
                file.unlink()
        for dir in reversed(list(duplicates_dir.glob("**/*"))):
            if dir.is_dir():
                dir.rmdir()
        duplicates_dir.rmdir()


def test_parse_args_default_mode() -> None:
    args = parse_args(["path/to/file"])
    assert args.mode == "interactive"
    assert args.threshold == 0.85
    assert args.paths == ["path/to/file"]


def test_scan_paths_with_text_file(tmp_path: Path) -> None:
    # Create a test text file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    # Scan the directory
    text_files = scan_paths([str(tmp_path)], min_printable_ratio=0.8)

    assert len(text_files) == 1
    assert text_files[0].path == test_file
    assert text_files[0].size == len("Hello, World!")


def test_scan_paths_with_non_text_file(tmp_path: Path) -> None:
    # Create a test binary file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(bytes([0x00, 0x01, 0x02, 0x03]))

    # Scan the directory
    text_files = scan_paths([str(tmp_path)], min_printable_ratio=0.8)

    assert len(text_files) == 0


def test_scan_paths_with_mixed_files(tmp_path: Path) -> None:
    # Create a text file
    text_file = tmp_path / "test.txt"
    text_file.write_text("Hello, World!")

    # Create a binary file
    bin_file = tmp_path / "test.bin"
    bin_file.write_bytes(bytes([0x00, 0x01, 0x02, 0x03]))

    # Create a subdirectory with a text file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    subtext_file = subdir / "subtest.txt"
    subtext_file.write_text("Hello from subdir!")

    # Scan the directory
    text_files = scan_paths([str(tmp_path)], min_printable_ratio=0.8)

    assert len(text_files) == 2
    paths = {tf.path for tf in text_files}
    assert paths == {text_file, subtext_file}


def test_parse_args_minhash_config() -> None:
    args = parse_args(["path/to/file", "--num-perm", "256", "--shingle-size", "3"])
    assert args.num_perm == 256
    assert args.shingle_size == 3


def test_parse_args_default_minhash_config() -> None:
    args = parse_args(["path/to/file"])
    assert args.num_perm == 128
    assert args.shingle_size == 5


def test_scan_paths_with_minhash_config(tmp_path: Path) -> None:
    # Create a test text file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    # Scan with custom MinHash config
    text_files = scan_paths(
        [str(tmp_path)], min_printable_ratio=0.8, num_perm=256, shingle_size=3
    )

    assert len(text_files) == 1
    assert text_files[0].path == test_file
    assert text_files[0].has_signature()


def test_prepare_moves_flat_structure(tmp_path: Path) -> None:
    """Test move preparation with flat directory structure."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content")
    file2.write_text("content")

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=False,
    )

    assert len(moves) == 1  # One file should be kept, one moved
    assert moves[0].destination.parent == tmp_path / "duplicates"


def test_prepare_moves_preserved_structure(tmp_path: Path) -> None:
    """Test move preparation with preserved directory structure."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    file1 = dir1 / "test.txt"
    file2 = dir2 / "test.txt"
    file1.write_text("content")
    file2.write_text("content")

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 1  # One file should be kept, one moved
    moved_file = moves[0]
    assert "dir1" in str(moved_file.destination) or "dir2" in str(
        moved_file.destination
    )


def test_prepare_moves_name_conflicts(tmp_path: Path) -> None:
    """Test handling of name conflicts in move preparation."""
    file1 = tmp_path / "test.txt"
    file2 = tmp_path / "subdir" / "test.txt"
    file1.write_text("content")
    file2.parent.mkdir()
    file2.write_text("content")

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 1  # One file should be kept, one moved
    # Verify the moved file maintains its structure
    assert (
        moves[0].destination.parent == (tmp_path / "duplicates" / "subdir")
        or moves[0].destination.parent == tmp_path / "duplicates"
    )


def test_prepare_moves_single_file_multiple_levels(tmp_path: Path) -> None:
    """Test move preparation with single file in nested structure."""
    nested_dir = tmp_path / "a" / "b" / "c"
    nested_dir.mkdir(parents=True)
    file1 = nested_dir / "test.txt"
    file2 = tmp_path / "test.txt"
    file1.write_text("content")
    file2.write_text("content")

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 1  # One file should be kept, one moved


def test_prepare_moves_mixed_depths(tmp_path: Path) -> None:
    """Test move preparation with files at different depths."""
    # Create files at different depths
    file1 = tmp_path / "test.txt"
    file2 = tmp_path / "a" / "test.txt"
    file3 = tmp_path / "a" / "b" / "test.txt"

    file1.write_text("content")
    file2.parent.mkdir()
    file2.write_text("content")
    file3.parent.mkdir(parents=True)
    file3.write_text("content")

    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 2  # Two files should be moved, one kept


def test_prepare_moves_special_characters(tmp_path: Path) -> None:
    """Test move preparation with special characters in paths."""
    # Create files with special characters in names
    file1 = tmp_path / "test space.txt"
    file2 = tmp_path / "test#hash.txt"
    file3 = tmp_path / "test@symbol.txt"

    file1.write_text("content")
    file2.write_text("content")
    file3.write_text("content")

    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 2  # Two files should be moved, one kept


def test_prepare_moves_case_sensitivity(tmp_path: Path) -> None:
    """Test move preparation with case-sensitive paths."""
    file1 = tmp_path / "test.txt"
    file2 = tmp_path / "Test.txt"
    file3 = tmp_path / "TEST.txt"

    file1.write_text("content")
    file2.write_text("content")
    file3.write_text("content")

    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 2  # Two files should be moved, one kept


def test_prepare_moves_arbitrary_depth(tmp_path: Path) -> None:
    """Test move preparation with arbitrary directory depth."""
    # Create a deep directory structure
    deep_dir = tmp_path
    for i in range(10):  # Create 10 levels
        deep_dir = deep_dir / f"level{i}"
    deep_dir.mkdir(parents=True)

    file1 = deep_dir / "test.txt"
    file2 = tmp_path / "test.txt"
    file1.write_text("content")
    file2.write_text("content")

    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=tmp_path / "duplicates",
        preserve_structure=True,
        base_dir=tmp_path,
    )

    assert len(moves) == 1  # One file should be kept, one moved


def test_execute_moves_dry_run(tmp_path: Path) -> None:
    """Test that dry run mode doesn't actually move files."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file1.write_text("content1")
    file2 = tmp_path / "test2.txt"
    file2.write_text("content2")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=False,
        group_id=1,
    )

    # Create UI with dry run config
    console = Console(force_terminal=True)
    move_config = MoveConfig(holding_dir=holding_dir, dry_run=True)
    ui = InteractiveUI(console=console, move_config=move_config)

    # Display move preview and execute in dry run mode
    ui.display_move_preview(moves)
    if not ui.move_config.dry_run:
        execute_moves(moves)

    # Check that files haven't moved
    assert file1.exists()
    assert file2.exists()
    assert not holding_dir.exists()


def test_prepare_moves_empty_list(tmp_path: Path) -> None:
    """Test move preparation with empty file list."""
    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[], holding_dir=holding_dir, preserve_structure=True, group_id=1
    )
    assert len(moves) == 0


def test_non_interactive_mode_basic(tmp_path: Path) -> None:
    """Test basic non-interactive mode functionality."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],  # Pass paths instead of text_files
        threshold=0.8,
        base_dir=tmp_path,
        holding_dir=tmp_path / "duplicates",
        dry_run=False,
    )
    assert result == 0


def test_non_interactive_mode_with_retention(tmp_path: Path) -> None:
    """Test non-interactive mode with retention configuration."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    retention_config = RetentionConfig(
        strategy="newest",
        priority_paths=[str(tmp_path)],
        priority_first=True,
    )

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],  # Pass paths instead of text_files
        threshold=0.8,
        base_dir=tmp_path,
        holding_dir=tmp_path / "duplicates",
        retention_config=retention_config,
    )
    assert result == 0


def test_non_interactive_mode_dry_run(tmp_path: Path) -> None:
    """Test non-interactive mode with dry run option."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],
        threshold=0.8,
        base_dir=tmp_path,
        holding_dir=tmp_path / "duplicates",
        dry_run=True,
    )
    assert result == 0
    assert (tmp_path / "duplicates").exists() is False


def test_non_interactive_mode_with_error(tmp_path: Path) -> None:
    """Test non-interactive mode error handling."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    console = Console(force_terminal=True)
    with patch(
        "ndetect.cli.execute_moves",
        side_effect=FileOperationError("Test error", str(file1), "move"),
    ):
        result = handle_non_interactive_mode(
            console=console,
            paths=[str(tmp_path)],
            threshold=0.8,
            base_dir=tmp_path,
            holding_dir=tmp_path / "duplicates",
        )
    assert result == 1


def test_non_interactive_mode_with_logging(tmp_path: Path) -> None:
    """Test non-interactive mode with logging enabled."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("test content")
    file2.write_text("test content")

    log_file = tmp_path / "test.log"
    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],
        threshold=0.8,
        base_dir=tmp_path,
        holding_dir=tmp_path / "duplicates",
        log_file=log_file,
    )
    assert result == 0
    assert log_file.exists()


def test_non_interactive_mode_no_duplicates(tmp_path: Path) -> None:
    """Test non-interactive mode when no duplicates are found."""
    # Create test files with different content
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("content 1")
    file2.write_text("content 2")

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        paths=[str(tmp_path)],
        threshold=0.8,
        base_dir=tmp_path,
        holding_dir=tmp_path / "duplicates",
    )
    assert result == 0
    assert not (tmp_path / "duplicates").exists()


def test_process_group_similarities(tmp_path: Path) -> None:
    """Test that process_group correctly shows similarities."""
    # Create test files with known similarity
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("hello world")
    file2.write_text("hello world")  # Identical content for predictable similarity

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    # Build graph
    graph = SimilarityGraph(threshold=0.5)
    graph.add_files(text_files)
    groups = graph.get_groups()

    console = Console(force_terminal=True)
    ui = InteractiveUI(
        console=console,
        move_config=MoveConfig(holding_dir=Path("holding")),
    )

    # Mock prompt_for_action using Mock
    mock_prompt = Mock(side_effect=[Action.SIMILARITIES, Action.QUIT])
    ui.prompt_for_action = mock_prompt  # type: ignore

    # Spy on show_similarities to verify it's called with correct data
    show_similarities_calls = []
    original_show_similarities = ui.show_similarities

    def spy_show_similarities(*args: Any, **kwargs: Any) -> Any:
        show_similarities_calls.append((args, kwargs))
        return original_show_similarities(*args, **kwargs)

    ui.show_similarities = spy_show_similarities  # type: ignore

    # Run the process
    process_group(ui, graph, groups[0])

    # Verify show_similarities was called with correct data
    assert len(show_similarities_calls) == 1
    call_args, call_kwargs = show_similarities_calls[0]

    # Verify the files were passed
    assert len(call_args) >= 1
    files_arg = call_args[0]
    assert all(isinstance(f, Path) for f in files_arg)
    assert len(files_arg) == 2
    assert {f.name for f in files_arg} == {"test1.txt", "test2.txt"}

    # Verify similarities were passed
    similarities = call_args[1]
    assert len(similarities) == 1  # One pair of files
    file_pair, similarity = next(iter(similarities.items()))
    assert similarity == 1.0  # Identical files should have 100% similarity

    # Verify prompt was called twice
    assert mock_prompt.call_count == 2


def test_non_interactive_mode_with_symlinks(tmp_path: Path) -> None:
    """Test non-interactive mode handling of symlinks."""
    # Create original files
    original1 = tmp_path / "original1.txt"
    original2 = tmp_path / "original2.txt"
    original1.write_text("content1")
    original2.write_text("content2")

    # Create symlinks
    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"
    link1.symlink_to(original1)
    link2.symlink_to(original2)

    text_files = scan_paths(
        [str(tmp_path)],
        min_printable_ratio=0.8,
        follow_symlinks=True,  # New parameter
    )

    # Should find both originals and symlinks
    assert len(text_files) == 4
    paths = {f.path for f in text_files}
    assert original1 in paths
    assert original2 in paths
    assert link1 in paths
    assert link2 in paths


def test_parse_args_symlink_options() -> None:
    """Test parsing of symlink-related arguments."""
    # Test default behavior
    args = parse_args(["path/to/file"])
    assert args.follow_symlinks is True

    # Test explicit enable
    args = parse_args(["--follow-symlinks", "path/to/file"])
    assert args.follow_symlinks is True

    # Test explicit disable
    args = parse_args(["--no-follow-symlinks", "path/to/file"])
    assert args.follow_symlinks is False


def test_scan_paths_symlink_behavior(tmp_path: Path) -> None:
    """Test symlink behavior in scan_paths."""
    # Create original file
    original = tmp_path / "original.txt"
    original.write_text("Hello, World!")

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    # Test with symlinks enabled (default)
    files = scan_paths([str(tmp_path)], follow_symlinks=True)
    paths = {f.path for f in files}
    assert len(paths) == 2
    assert original in paths
    assert link in paths

    # Test with symlinks disabled
    files = scan_paths([str(tmp_path)], follow_symlinks=False)
    paths = {f.path for f in files}
    assert len(paths) == 1
    assert original in paths
    assert link not in paths


def test_scan_paths_with_empty_files(tmp_path: Path) -> None:
    """Test handling of empty files."""
    # Create a regular text file
    text_file = tmp_path / "test.txt"
    text_file.write_text("Hello, World!")

    # Create an empty file
    empty_file = tmp_path / "empty.txt"
    empty_file.touch()

    # Test with default settings (skip empty)
    text_files = scan_paths([str(tmp_path)], min_printable_ratio=0.8)
    assert len(text_files) == 1
    assert text_files[0].path == text_file

    # Test with empty files included
    text_files = scan_paths([str(tmp_path)], min_printable_ratio=0.8, skip_empty=False)
    assert len(text_files) == 2
    paths = {tf.path for tf in text_files}
    assert paths == {text_file, empty_file}
