"""Tests for SymlinkHandler functionality."""

from pathlib import Path

import pytest

from ndetect.symlinks import SymlinkConfig, SymlinkHandler


def test_symlink_handler_basic(tmp_path: Path) -> None:
    """Test basic symlink resolution."""
    handler = SymlinkHandler(SymlinkConfig())

    # Create original file and symlink
    original = tmp_path / "original.txt"
    original.write_text("content")
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    resolved = handler.resolve(link)
    assert resolved == original


def test_symlink_handler_disabled(tmp_path: Path) -> None:
    """Test handler when symlinks are disabled."""
    handler = SymlinkHandler(SymlinkConfig(follow_symlinks=False))

    original = tmp_path / "original.txt"
    original.write_text("content")
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    assert handler.resolve(link) is None


def test_symlink_handler_nested(tmp_path: Path) -> None:
    """Test nested symlink resolution."""
    handler = SymlinkHandler(SymlinkConfig())

    # Create chain: link1 -> link2 -> link3 -> original
    original = tmp_path / "original.txt"
    original.write_text("content")

    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"
    link3 = tmp_path / "link3.txt"

    link3.symlink_to(original)
    link2.symlink_to(link3)
    link1.symlink_to(link2)

    resolved = handler.resolve(link1)
    assert resolved == original


def test_symlink_handler_circular(tmp_path: Path) -> None:
    """Test circular symlink detection."""
    handler = SymlinkHandler(SymlinkConfig())

    # Create circular reference: link1 -> link2 -> link1
    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"

    link1.symlink_to(link2)
    link2.symlink_to(link1)

    assert handler.resolve(link1) is None


def test_symlink_handler_max_depth(tmp_path: Path) -> None:
    """Test max depth limit enforcement."""
    # Create a chain deeper than default max_depth
    original = tmp_path / "original.txt"
    original.write_text("content")

    current = original
    links = []
    for i in range(12):  # Default max_depth is 10
        link = tmp_path / f"link{i}.txt"
        link.symlink_to(current)
        links.append(link)
        current = link

    # Should fail with default depth
    default_handler = SymlinkHandler(SymlinkConfig())
    assert default_handler.resolve(links[-1]) is None

    # Should succeed with higher depth limit
    deep_handler = SymlinkHandler(SymlinkConfig(max_depth=15))
    assert deep_handler.resolve(links[-1]) == original


def test_symlink_handler_base_dir_security(tmp_path: Path) -> None:
    """Test base directory security constraints."""
    base_dir = tmp_path / "base"
    outside_dir = tmp_path / "outside"
    base_dir.mkdir()
    outside_dir.mkdir()

    # Create file outside base directory
    outside_file = outside_dir / "target.txt"
    outside_file.write_text("content")

    # Create symlink inside base pointing outside
    inside_link = base_dir / "link.txt"
    inside_link.symlink_to(outside_file)

    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    assert handler.resolve(inside_link) is None


def test_symlink_handler_relative_paths(tmp_path: Path) -> None:
    """Test handling of relative symlinks."""
    handler = SymlinkHandler(SymlinkConfig())

    # Create nested directory structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    original = tmp_path / "original.txt"
    original.write_text("content")

    # Create relative symlink from subdir
    link = subdir / "link.txt"
    link.symlink_to(Path("../original.txt"))

    resolved = handler.resolve(link)
    assert resolved == original


@pytest.mark.skipif(
    not hasattr(Path, "hardlink_to"),
    reason="hardlink_to not supported on this platform",
)
def test_symlink_handler_hardlinks(tmp_path: Path) -> None:
    """Test handling of hard links."""
    handler = SymlinkHandler(SymlinkConfig())

    original = tmp_path / "original.txt"
    original.write_text("content")
    hardlink = tmp_path / "hardlink.txt"
    hardlink.hardlink_to(original)

    # Hard links should be treated as regular files
    assert handler.resolve(hardlink) == hardlink


def test_symlink_handler_nonexistent(tmp_path: Path) -> None:
    """Test handling of broken symlinks."""
    handler = SymlinkHandler(SymlinkConfig())

    link = tmp_path / "broken.txt"
    link.symlink_to(tmp_path / "nonexistent.txt")

    assert handler.resolve(link) is None
