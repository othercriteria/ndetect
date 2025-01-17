"""Tests for SymlinkHandler functionality."""

from pathlib import Path

from ndetect.symlinks import SymlinkConfig, SymlinkHandler


def test_symlink_handler_basic(tmp_path: Path) -> None:
    """Test basic symlink resolution."""
    handler = SymlinkHandler(SymlinkConfig())

    original = tmp_path / "original.txt"
    original.write_text("content")
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    resolved = handler.resolve(link)
    assert resolved == original


def test_symlink_handler_base_dir(tmp_path: Path) -> None:
    """Test symlink resolution within base directory."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    original = base_dir / "original.txt"
    original.write_text("content")
    link = base_dir / "link.txt"
    link.symlink_to(original.name)  # Use relative path within base_dir

    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    resolved = handler.resolve(link)
    assert resolved == original


def test_symlink_handler_base_dir_security(tmp_path: Path) -> None:
    """Test base directory security constraints."""
    base_dir = tmp_path / "base"
    outside_dir = tmp_path / "outside"
    base_dir.mkdir()
    outside_dir.mkdir()

    outside_file = outside_dir / "target.txt"
    outside_file.write_text("content")

    inside_link = base_dir / "link.txt"
    inside_link.symlink_to(outside_file)

    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    assert handler.resolve(inside_link) is None


def test_symlink_handler_nested(tmp_path: Path) -> None:
    """Test nested symlink resolution."""
    handler = SymlinkHandler(SymlinkConfig())

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


def test_symlink_handler_max_depth(tmp_path: Path) -> None:
    """Test max depth limit enforcement."""
    handler = SymlinkHandler(SymlinkConfig())

    original = tmp_path / "original.txt"
    original.write_text("content")

    current = original
    links = []
    for i in range(9):  # Create chain of 9 links (within default max_depth=10)
        link = tmp_path / f"link{i}.txt"
        link.symlink_to(current)
        links.append(link)
        current = link

    # Should succeed within depth limit
    assert handler.resolve(links[-1]) == original

    # Add one more link to exceed default depth
    final_link = tmp_path / "final.txt"
    final_link.symlink_to(links[-1])
    assert handler.resolve(final_link) is None


def test_symlink_handler_relative_paths(tmp_path: Path) -> None:
    """Test handling of relative symlinks."""
    handler = SymlinkHandler(SymlinkConfig())

    subdir = tmp_path / "subdir"
    subdir.mkdir()

    original = tmp_path / "original.txt"
    original.write_text("content")

    link = subdir / "link.txt"
    link.symlink_to(Path("../original.txt"))

    resolved = handler.resolve(link)
    assert resolved == original
