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
    """Test base directory containment."""
    base_dir = tmp_path / "base"
    outside_dir = tmp_path / "outside"
    base_dir.mkdir()
    outside_dir.mkdir()

    # Create a file outside the base directory
    target = outside_dir / "target.txt"
    target.write_text("content")

    # Create a symlink inside base_dir pointing outside
    link = base_dir / "link.txt"
    link.symlink_to(target)

    # With base_dir set, should reject symlinks pointing outside
    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    assert handler.resolve(link) is None

    # Without base_dir, should allow the symlink
    unrestricted_handler = SymlinkHandler(SymlinkConfig())
    assert unrestricted_handler.resolve(link) == target


def test_symlink_handler_base_dir_nested(tmp_path: Path) -> None:
    """Test base directory containment with nested symlinks."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    # Create nested structure inside base_dir
    sub_dir = base_dir / "sub"
    sub_dir.mkdir()

    # Create target file inside base_dir
    target = base_dir / "target.txt"
    target.write_text("content")

    # Create nested symlinks
    link1 = sub_dir / "link1.txt"
    link2 = sub_dir / "link2.txt"

    link2.symlink_to(target)
    link1.symlink_to(link2)

    # Should allow nested symlinks within base_dir
    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    assert handler.resolve(link1) == target


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
    """Test max depth limit for symlink chains."""
    # Create a chain of symlinks
    files = [tmp_path / f"file{i}.txt" for i in range(12)]
    files[0].write_text("content")

    # Create a chain: file11 -> file10 -> ... -> file1 -> file0
    for i in range(11, 0, -1):
        files[i].symlink_to(files[i - 1])

    # Test with default depth (10)
    handler = SymlinkHandler(SymlinkConfig())
    assert handler.resolve(files[9]) == files[0]  # Should resolve (depth 9)
    assert handler.resolve(files[10]) is None  # Should fail (depth 10)

    # Test with custom depth
    handler = SymlinkHandler(SymlinkConfig(max_depth=5))
    assert handler.resolve(files[4]) == files[0]  # Should resolve (depth 4)
    assert handler.resolve(files[5]) is None  # Should fail (depth 5)


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


def test_symlink_handler_dot_dot_containment(tmp_path: Path) -> None:
    """Test handling of .. in paths with base directory containment."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text("content")

    link = base_dir / "link.txt"
    link.symlink_to("../outside.txt")

    # With base_dir set, should reject symlinks pointing outside
    handler = SymlinkHandler(SymlinkConfig(base_dir=base_dir))
    assert handler.resolve(link) is None

    # Without base_dir, should allow the symlink
    unrestricted_handler = SymlinkHandler(SymlinkConfig())
    assert unrestricted_handler.resolve(link) == outside


def test_symlink_handler_security_modes(tmp_path: Path) -> None:
    """Test comprehensive symlink security configurations."""
    base_dir = tmp_path / "base"
    outside_dir = tmp_path / "outside"
    base_dir.mkdir()
    outside_dir.mkdir()

    # Create files and symlinks for testing
    inside_target = base_dir / "inside.txt"
    outside_target = outside_dir / "outside.txt"
    outside_root = tmp_path / "outside.txt"
    inside_target.write_text("inside content")
    outside_target.write_text("outside content")
    outside_root.write_text("root content")

    # Create different types of symlinks
    abs_inside_link = base_dir / "abs_inside.txt"
    abs_outside_link = base_dir / "abs_outside.txt"
    rel_inside_link = base_dir / "rel_inside.txt"
    rel_outside_link = base_dir / "rel_outside.txt"
    dotdot_link = base_dir / "dotdot.txt"

    abs_inside_link.symlink_to(inside_target.absolute())
    abs_outside_link.symlink_to(outside_target.absolute())
    rel_inside_link.symlink_to("inside.txt")
    rel_outside_link.symlink_to("../outside/outside.txt")
    dotdot_link.symlink_to("../outside.txt")

    # Test cases for different security configurations
    test_cases = [
        # (config, link, expected_result)
        # Default config - allows everything
        (SymlinkConfig(), abs_inside_link, inside_target),
        (SymlinkConfig(), abs_outside_link, outside_target),
        (SymlinkConfig(), rel_inside_link, inside_target),
        (SymlinkConfig(), rel_outside_link, outside_target),
        (SymlinkConfig(), dotdot_link, outside_root),
        # Base dir containment
        (SymlinkConfig(base_dir=base_dir), abs_inside_link, inside_target),
        (SymlinkConfig(base_dir=base_dir), abs_outside_link, None),
        (SymlinkConfig(base_dir=base_dir), rel_inside_link, inside_target),
        (SymlinkConfig(base_dir=base_dir), rel_outside_link, None),
        (SymlinkConfig(base_dir=base_dir), dotdot_link, None),
    ]

    for config, link, expected in test_cases:
        handler = SymlinkHandler(config)
        result = handler.resolve(link)
        assert result == expected, (
            f"Failed with config={config}, link={link.name}\n"
            f"Expected: {expected}\n"
            f"Got: {result}"
        )
