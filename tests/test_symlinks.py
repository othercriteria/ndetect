import os
from pathlib import Path
from typing import Callable

import pytest

from ndetect.analysis import FileAnalyzer
from ndetect.models import FileAnalyzerConfig
from ndetect.symlinks import resolve_symlink


def test_symlink_to_text_file(
    tmp_path: Path, create_file_with_content: Callable[[str, str], Path]
) -> None:
    """Test analyzing a symlink pointing to a valid text file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file using fixture
    original = create_file_with_content("original.txt", "Hello, World!")

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    result = analyzer.analyze_file(link)
    assert result is not None
    assert result.path == link
    assert result.has_signature()


def test_symlink_to_binary_file(
    tmp_path: Path, create_file_with_content: Callable[[str, str], Path]
) -> None:
    """Test analyzing a symlink pointing to a binary file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create binary file using fixture and write binary content
    binary = create_file_with_content("binary.dat", "")
    binary.write_bytes(bytes([0x00, 0xFF] * 100))

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(binary)

    result = analyzer.analyze_file(link)
    assert result is None


def test_broken_symlink(tmp_path: Path) -> None:
    """Test analyzing a broken symlink."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create symlink to non-existent file
    link = tmp_path / "broken.txt"
    link.symlink_to(tmp_path / "nonexistent.txt")

    result = analyzer.analyze_file(link)
    assert result is None


def test_circular_symlink(tmp_path: Path) -> None:
    """Test handling of circular symlinks."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create circular symlink
    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"
    link1.symlink_to(link2)
    link2.symlink_to(link1)

    result = analyzer.analyze_file(link1)
    assert result is None


@pytest.mark.skipif(os.name == "nt", reason="Requires Unix-like OS")
def test_symlink_permissions(tmp_path: Path) -> None:
    """Test symlink with different permission scenarios."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file with restricted permissions
    original = tmp_path / "restricted.txt"
    original.write_text("Secret content")
    original.chmod(0o000)

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    try:
        result = analyzer.analyze_file(link)
        assert result is None
    finally:
        # Restore permissions for cleanup
        original.chmod(0o644)


def test_symlink_validation(tmp_path: Path) -> None:
    """Test different symlink validation scenarios."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create test files and directories
    text_file = tmp_path / "source.txt"
    text_file.write_text("Hello World")

    valid_link = tmp_path / "valid_link.txt"
    broken_link = tmp_path / "broken_link.txt"
    nested_link = tmp_path / "nested_link.txt"
    nested_target = tmp_path / "nested_target.txt"

    # Create valid symlink
    valid_link.symlink_to(text_file)

    # Create broken symlink
    broken_link.symlink_to(tmp_path / "nonexistent.txt")

    # Create nested symlinks
    nested_link.symlink_to(nested_target)
    nested_target.symlink_to(text_file)

    # Test valid symlink
    result = analyzer.analyze_file(valid_link)
    assert result is not None
    assert result.path == valid_link

    # Test broken symlink
    result = analyzer.analyze_file(broken_link)
    assert result is None

    # Test nested symlinks
    result = analyzer.analyze_file(nested_link)
    assert result is not None
    assert result.path == nested_link

    # Test non-symlink file
    result = analyzer.analyze_file(text_file)
    assert result is not None
    assert result.path == text_file


def test_resolve_symlink_basic(tmp_path: Path) -> None:
    """Test basic symlink resolution."""
    original = tmp_path / "original.txt"
    original.write_text("content")
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    resolved = resolve_symlink(link)
    assert resolved == original.resolve()


def test_resolve_symlink_nested(tmp_path: Path) -> None:
    """Test nested symlink resolution."""
    original = tmp_path / "original.txt"
    original.write_text("content")

    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"
    link3 = tmp_path / "link3.txt"

    link1.symlink_to(original)
    link2.symlink_to(link1)
    link3.symlink_to(link2)

    resolved = resolve_symlink(link3)
    assert resolved == original.resolve()


def test_resolve_symlink_circular(tmp_path: Path) -> None:
    """Test circular symlink detection."""
    link1 = tmp_path / "link1.txt"
    link2 = tmp_path / "link2.txt"

    link1.symlink_to(link2)
    link2.symlink_to(link1)

    assert resolve_symlink(link1) is None


def test_resolve_symlink_max_depth(tmp_path: Path) -> None:
    """Test max depth limit."""
    original = tmp_path / "original.txt"
    original.write_text("content")

    current = original
    links = []

    # Create chain of 15 symlinks
    for i in range(15):
        link = tmp_path / f"link{i}.txt"
        link.symlink_to(current)
        links.append(link)
        current = link

    # Should fail with default max_depth=10
    assert resolve_symlink(links[-1]) is None

    # Should succeed with higher max_depth
    assert resolve_symlink(links[-1], max_depth=20) == original.resolve()


def test_resolve_symlink_relative(tmp_path: Path) -> None:
    """Test relative symlink resolution."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    original = tmp_path / "original.txt"
    original.write_text("content")

    link = subdir / "link.txt"
    link.symlink_to(Path("../original.txt"))

    resolved = resolve_symlink(link)
    assert resolved == original.resolve()


def test_resolve_symlink_broken(tmp_path: Path) -> None:
    """Test broken symlink handling."""
    link = tmp_path / "broken.txt"
    link.symlink_to(tmp_path / "nonexistent.txt")

    assert resolve_symlink(link) is None
