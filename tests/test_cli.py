from pathlib import Path
from ndetect.cli import parse_args, scan_paths


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