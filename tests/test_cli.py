import shutil
from pathlib import Path
from typing import Any, Generator, List

import pytest
from rich.console import Console

from ndetect.cli import handle_non_interactive_mode, parse_args, scan_paths
from ndetect.models import MoveConfig, TextFile
from ndetect.operations import MoveOperation, execute_moves, prepare_moves
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


def test_non_interactive_mode(
    tmp_path: Path, duplicates_dir: Path, monkeypatch: Any
) -> None:
    """Test non-interactive mode basic functionality."""
    # Create test files with identical content
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    content = "hello world this is a test"
    file1.write_text(content)
    file2.write_text(content)

    # Remember original files for later comparison
    original_files = {file1, file2}

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    moves_executed: List[MoveOperation] = []

    def mock_execute_moves(moves: List[MoveOperation]) -> None:
        for move in moves:
            moves_executed.append(move)
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.destination))

    monkeypatch.setattr("ndetect.cli.execute_moves", mock_execute_moves)

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        text_files=text_files,
        threshold=0.5,
        base_dir=tmp_path,
        holding_dir=duplicates_dir,
    )

    assert result == 0, "Expected successful execution"

    # Verify exactly one file was moved to duplicates
    moved_files = list(duplicates_dir.glob("**/*.txt"))
    assert len(moved_files) == 1, f"Expected 1 moved file, got {len(moved_files)}"

    # Verify exactly one file remains in original location
    remaining_files = list(tmp_path.glob("*.txt"))
    assert (
        len(remaining_files) == 1
    ), f"Expected 1 remaining file, got {len(remaining_files)}"

    # Verify the remaining file is one of the original files
    assert (
        remaining_files[0] in original_files
    ), "Remaining file should be one of the originals"

    # Verify total number of files is still 2
    total_files = len(moved_files) + len(remaining_files)
    assert total_files == 2, f"Expected 2 total files, got {total_files}"


def test_non_interactive_mode_dry_run(tmp_path: Path) -> None:
    """Test that dry run mode doesn't move files."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("hello world this is a test")
    file2.write_text("hello world this is also a test")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console, text_files=text_files, threshold=0.7, dry_run=True
    )

    assert result == 0
    # Check that files weren't moved
    assert file1.exists()
    assert file2.exists()
    assert not Path("duplicates").exists()


def test_non_interactive_mode_no_similar_files(tmp_path: Path) -> None:
    """Test behavior when no similar files are found."""
    # Create test files with different content
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    file1.write_text("hello world")
    file2.write_text("completely different content")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console, text_files=text_files, threshold=0.7, dry_run=False
    )

    assert result == 0
    # Check that no files were moved
    assert file1.exists()
    assert file2.exists()
    assert not Path("duplicates").exists()


def test_non_interactive_mode_with_logging(
    tmp_path: Path, duplicates_dir: Path, monkeypatch: Any
) -> None:
    """Test non-interactive mode with logging enabled."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    log_file = tmp_path / "test.log"

    file1.write_text("test content")
    file2.write_text("test content")

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    moves_executed: List[MoveOperation] = []

    def mock_execute_moves(moves: List[MoveOperation]) -> None:
        for move in moves:
            moves_executed.append(move)
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.destination))

    monkeypatch.setattr("ndetect.cli.execute_moves", mock_execute_moves)

    # Create log file directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        text_files=text_files,
        threshold=0.5,
        base_dir=tmp_path,
        holding_dir=duplicates_dir,
        log_file=log_file,
    )

    assert result == 0
    assert len(moves_executed) > 0

    # Check log content
    log_content = log_file.read_text()

    # Look for structured log entries
    assert '"operation": "move"' in log_content, "Log should contain move operation"
    assert (
        '"status": "success"' in log_content
    ), "Log should indicate successful completion"
    assert str(file2.name) in log_content, "Log should contain moved file name"


def test_non_interactive_mode_error_handling(
    tmp_path: Path, monkeypatch: Any, cleanup_duplicates: None
) -> None:
    """Test error handling during file operations."""
    # Create test files with identical content
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    content = "hello world this is a test"
    file1.write_text(content)
    file2.write_text(content)

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    # Mock execute_moves to raise an error
    def mock_execute_moves(moves: List[MoveOperation]) -> None:
        raise OSError("Permission denied")

    # Need to patch where it's used, not where it's defined
    monkeypatch.setattr("ndetect.cli.execute_moves", mock_execute_moves)

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console, text_files=text_files, threshold=0.5, base_dir=tmp_path
    )

    assert result == 1  # Should return error code
    # Check that files weren't moved
    assert file1.exists()
    assert file2.exists()
    # Ensure duplicates directory wasn't created
    assert not Path("duplicates").exists()
