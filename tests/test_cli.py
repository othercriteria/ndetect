import logging
from pathlib import Path
from typing import Any, Generator, List

import pytest
from rich.console import Console

from ndetect.cli import handle_non_interactive_mode, parse_args, scan_paths
from ndetect.logging import setup_logging
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
    """Test move preparation with flat structure."""
    # Create test files in nested directories
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file1 = dir1 / "test1.txt"
    file1.write_text("content1")

    dir2 = tmp_path / "dir2" / "subdir"
    dir2.mkdir(parents=True)
    file2 = dir2 / "test2.txt"
    file2.write_text("content2")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=False,
        group_id=1,
    )

    assert len(moves) == 2
    assert all(m.destination.parent == holding_dir for m in moves)
    assert {m.destination.name for m in moves} == {"test1.txt", "test2.txt"}


def test_prepare_moves_preserved_structure(tmp_path: Path) -> None:
    """Test move preparation with preserved directory structure."""
    # Create test files in nested directories
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file1 = dir1 / "test1.txt"
    file1.write_text("content1")

    dir2 = tmp_path / "dir2" / "subdir"
    dir2.mkdir(parents=True)
    file2 = dir2 / "test2.txt"
    file2.write_text("content2")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1,
    )

    assert len(moves) == 2
    # Check that relative paths are preserved
    assert moves[0].destination == holding_dir / "dir1" / "test1.txt"
    assert moves[1].destination == holding_dir / "dir2" / "subdir" / "test2.txt"


def test_prepare_moves_name_conflicts(tmp_path: Path) -> None:
    """Test that prepare_moves handles filename conflicts correctly."""
    # Create test files with same names in different directories
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    file1 = dir1 / "test.txt"
    file2 = dir2 / "test.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=False,  # Force name conflict
        group_id=1,
    )

    # Check that destinations are unique
    destinations = [move.destination for move in moves]
    assert len(destinations) == len(set(destinations))  # No duplicates
    assert all(move.destination.name.startswith("test") for move in moves)
    assert any(
        "_1" in str(move.destination) for move in moves
    )  # One file should be renamed


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


def test_prepare_moves_single_file_multiple_levels(tmp_path: Path) -> None:
    """Test prepare_moves with a single file in a deep directory structure."""
    # Create nested directories
    nested_dir = tmp_path / "a" / "b" / "c"
    nested_dir.mkdir(parents=True)

    # Create test file
    test_file = nested_dir / "test.txt"
    test_file.write_text("content")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[test_file],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1,
        base_dir=tmp_path,  # Pass the temp directory as base
    )

    assert len(moves) == 1
    assert moves[0].source == test_file
    # Should preserve directory structure under holding dir
    expected_dest = holding_dir / "a" / "b" / "c" / "test.txt"
    assert moves[0].destination == expected_dest


def test_prepare_moves_mixed_depths(tmp_path: Path) -> None:
    """Test preserving structure with files at different directory depths."""
    # Create files at different depths
    file1 = tmp_path / "a" / "test1.txt"
    file1.parent.mkdir(parents=True)
    file1.write_text("content1")

    file2 = tmp_path / "a" / "b" / "test2.txt"
    file2.parent.mkdir(parents=True)
    file2.write_text("content2")

    file3 = tmp_path / "test3.txt"
    file3.write_text("content3")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1,
    )

    assert len(moves) == 3
    destinations = {str(m.destination.relative_to(holding_dir)) for m in moves}
    assert destinations == {"test3.txt", "a/test1.txt", "a/b/test2.txt"}


def test_prepare_moves_special_characters(tmp_path: Path) -> None:
    """Test handling of special characters in filenames."""
    # Create files with special characters
    file1 = tmp_path / "test with spaces.txt"
    file1.write_text("content1")

    file2 = tmp_path / "test_with_#@!.txt"
    file2.write_text("content2")

    file3 = tmp_path / "测试文件.txt"  # Unicode filename
    file3.write_text("content3")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=holding_dir,
        preserve_structure=False,
        group_id=1,
    )

    assert len(moves) == 3
    # Check that special characters are preserved
    filenames = {m.destination.name for m in moves}
    assert "test with spaces.txt" in filenames
    assert "test_with_#@!.txt" in filenames
    assert "测试文件.txt" in filenames


def test_prepare_moves_case_sensitivity(tmp_path: Path) -> None:
    """Test handling of case-sensitive filenames."""
    # Create files with same name but different case
    file1 = tmp_path / "test.txt"
    file1.write_text("content1")

    file2 = tmp_path / "TEST.txt"
    file2.write_text("content2")

    file3 = tmp_path / "Test.txt"
    file3.write_text("content3")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file1, file2, file3],
        holding_dir=holding_dir,
        preserve_structure=False,
        group_id=1,
    )

    assert len(moves) == 3
    filenames = {m.destination.name for m in moves}
    # All files should get unique names
    assert len(filenames) == 3
    # Original case should be preserved
    assert all("test" in name.lower() for name in filenames)


def test_prepare_moves_arbitrary_depth(tmp_path: Path) -> None:
    """Test prepare_moves with arbitrary directory depth."""
    # Create random depth directory structure
    current_dir = tmp_path
    path_parts = ["gnkod", "eoboa", "zpqpb", "hbdkt", "oeqsz"]  # Random directory names

    for part in path_parts:
        current_dir = current_dir / part
        current_dir.mkdir()

    test_file = current_dir / "test.txt"
    test_file.write_text("content")

    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[test_file],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1,
        base_dir=tmp_path,  # Pass the temp directory as base
    )

    assert len(moves) == 1
    assert moves[0].source == test_file
    # Should preserve full directory structure
    expected_dest = holding_dir.joinpath(*path_parts) / "test.txt"
    assert moves[0].destination == expected_dest


def test_execute_moves_missing_source(tmp_path: Path) -> None:
    """Test handling of source file that disappears before move."""
    # Create test file
    file = tmp_path / "test.txt"
    file.write_text("content")

    move = MoveOperation(
        source=file, destination=tmp_path / "holding" / "test.txt", group_id=1
    )

    # Delete source file before move
    file.unlink()

    with pytest.raises(FileNotFoundError):
        execute_moves([move])


def test_non_interactive_mode(tmp_path: Path, cleanup_duplicates: None) -> None:
    """Test basic non-interactive mode operation."""
    # Create test files with identical content for guaranteed matching
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    content = "hello world this is a test"
    file1.write_text(content)
    file2.write_text(content)  # Identical content

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        text_files=text_files,
        threshold=0.5,  # More lenient threshold
        base_dir=tmp_path,  # Pass the temp directory as base
    )

    assert result == 0
    # Check that files were moved to duplicates directory
    duplicates_dir = Path("duplicates/group_1")  # Path is relative to current directory
    assert duplicates_dir.exists()
    assert (duplicates_dir / "test1.txt").exists()
    assert (duplicates_dir / "test2.txt").exists()


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
    tmp_path: Path, cleanup_duplicates: None
) -> None:
    """Test that operations are properly logged."""
    # Create log file and clear any existing handlers
    log_file = tmp_path / "test.log"
    logging.getLogger("ndetect").handlers.clear()

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

    # Setup logging
    setup_logging(log_file=log_file, verbose=True)

    console = Console(force_terminal=True)
    result = handle_non_interactive_mode(
        console=console,
        text_files=text_files,
        threshold=0.5,
        log_file=log_file,
        base_dir=tmp_path,  # Pass the temp directory as base
    )

    assert result == 0
    assert log_file.exists()
    log_content = log_file.read_text()
    # Check for expected log entries
    assert "Moving:" in log_content
    assert "Operation complete" in log_content


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
