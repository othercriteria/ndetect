import os
from pathlib import Path

from rich.console import Console

from ndetect.cli import handle_non_interactive_mode
from ndetect.models import RetentionConfig, TextFile
from ndetect.operations import select_keeper


def test_select_keeper_newest(tmp_path: Path) -> None:
    """Test selecting newest file as keeper."""
    # Create files with different timestamps
    file1 = tmp_path / "old.txt"
    file2 = tmp_path / "new.txt"

    file1.write_text("old")
    file2.write_text("new")

    # Set different modification times
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    config = RetentionConfig(strategy="newest")
    keeper = select_keeper([file1, file2], config)
    assert keeper == file2


def test_select_keeper_priority_paths(tmp_path: Path) -> None:
    """Test priority paths in keeper selection."""
    important = tmp_path / "important"
    other = tmp_path / "other"
    important.mkdir()
    other.mkdir()

    file1 = important / "test1.txt"
    file2 = other / "test2.txt"
    file1.write_text("content")
    file2.write_text("content")

    config = RetentionConfig(
        strategy="newest", priority_paths=["important/*"], priority_first=True
    )
    keeper = select_keeper([file1, file2], config)
    assert keeper == file1


def test_non_interactive_mode_with_retention(
    tmp_path: Path, cleanup_duplicates: None
) -> None:
    """Test non-interactive mode with retention criteria."""
    # Create test files with identical content
    file1 = tmp_path / "old.txt"
    file2 = tmp_path / "new.txt"
    content = "test content"
    file1.write_text(content)
    file2.write_text(content)

    # Set different timestamps
    os.utime(file1, (1000000, 1000000))
    os.utime(file2, (2000000, 2000000))

    text_files = [
        TextFile.from_path(file1, compute_minhash=True),
        TextFile.from_path(file2, compute_minhash=True),
    ]

    retention_config = RetentionConfig(strategy="oldest")
    console = Console(force_terminal=True)

    result = handle_non_interactive_mode(
        console=console,
        text_files=text_files,
        threshold=0.5,
        retention_config=retention_config,
        base_dir=tmp_path,
    )

    assert result == 0
    # Check that the older file remains and newer file is moved
    assert file1.exists()
    assert not file2.exists()
    assert (Path("duplicates") / "group_1" / "new.txt").exists()
