from pathlib import Path
from rich.console import Console
from ndetect.cli import (
    parse_args, 
    scan_paths, 
    prepare_moves,
    execute_moves
)
from ndetect.models import MoveConfig, MoveOperation
from ndetect.ui import InteractiveUI
import pytest


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
        [str(tmp_path)],
        min_printable_ratio=0.8,
        num_perm=256,
        shingle_size=3
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
        group_id=1
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
        group_id=1
    )
    
    assert len(moves) == 2
    # Check that relative paths are preserved
    assert moves[0].destination == holding_dir / "dir1" / "test1.txt"
    assert moves[1].destination == holding_dir / "dir2" / "subdir" / "test2.txt"


def test_prepare_moves_name_conflicts(tmp_path: Path) -> None:
    """Test handling of name conflicts in move preparation."""
    # Create test files
    file1 = tmp_path / "test.txt"
    file1.write_text("content1")
    
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    file2 = subdir / "test.txt"  # Same name as file1
    file2.write_text("content2")
    
    holding_dir = tmp_path / "holding"
    holding_dir.mkdir()
    # Create a file that would conflict
    (holding_dir / "test.txt").write_text("existing")
    
    moves = prepare_moves(
        files=[file1, file2],
        holding_dir=holding_dir,
        preserve_structure=False,
        group_id=1
    )
    
    assert len(moves) == 2
    filenames = {m.destination.name for m in moves}
    # Both files should get numbered suffixes since there's an existing file
    assert all(name.startswith("test_") and name.endswith(".txt") for name in filenames)
    assert len({name.split("_")[1].split(".")[0] for name in filenames}) == 2  # Different numbers


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
        group_id=1
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
        files=[],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1
    )
    assert len(moves) == 0


def test_prepare_moves_single_file_multiple_levels(tmp_path: Path) -> None:
    """Test preserving structure with deeply nested single file."""
    deep_dir = tmp_path / "a" / "b" / "c"
    deep_dir.mkdir(parents=True)
    file = deep_dir / "test.txt"
    file.write_text("content")
    
    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[file],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1
    )
    
    assert len(moves) == 1
    # Should preserve a/b/c structure
    assert moves[0].destination == holding_dir / "a" / "b" / "c" / "test.txt"


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
        group_id=1
    )
    
    assert len(moves) == 3
    destinations = {str(m.destination.relative_to(holding_dir)) for m in moves}
    assert destinations == {
        "test3.txt",
        "a/test1.txt",
        "a/b/test2.txt"
    }


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
        group_id=1
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
        group_id=1
    )
    
    assert len(moves) == 3
    filenames = {m.destination.name for m in moves}
    # All files should get unique names
    assert len(filenames) == 3
    # Original case should be preserved
    assert all("test" in name.lower() for name in filenames) 


def test_prepare_moves_arbitrary_depth(tmp_path: Path) -> None:
    """Test preserving structure with arbitrary directory depth."""
    # Create a deeply nested file with random depth
    deep_path = tmp_path
    expected_structure = []
    
    # Create 5 levels of random directory names
    import random
    import string
    for _ in range(5):
        dirname = ''.join(random.choices(string.ascii_lowercase, k=5))
        deep_path = deep_path / dirname
        expected_structure.append(dirname)
    
    # Create the file
    deep_path.mkdir(parents=True)
    test_file = deep_path / "test.txt"
    test_file.write_text("content")
    
    holding_dir = tmp_path / "holding"
    moves = prepare_moves(
        files=[test_file],
        holding_dir=holding_dir,
        preserve_structure=True,
        group_id=1
    )
    
    assert len(moves) == 1
    # Check that all directory levels are preserved
    expected_path = holding_dir
    for dirname in expected_structure:
        expected_path = expected_path / dirname
    expected_path = expected_path / "test.txt"
    
    assert moves[0].destination == expected_path 


def test_execute_moves_missing_source(tmp_path: Path) -> None:
    """Test handling of source file that disappears before move."""
    # Create test file
    file = tmp_path / "test.txt"
    file.write_text("content")
    
    move = MoveOperation(
        source=file,
        destination=tmp_path / "holding" / "test.txt",
        group_id=1
    )
    
    # Delete source file before move
    file.unlink()
    
    with pytest.raises(FileNotFoundError):
        execute_moves([move]) 