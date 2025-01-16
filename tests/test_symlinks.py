import os
from pathlib import Path

import pytest

from ndetect.analysis import FileAnalyzer
from ndetect.models import FileAnalyzerConfig


def test_symlink_to_text_file(tmp_path: Path) -> None:
    """Test analyzing a symlink pointing to a valid text file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create original file
    original = tmp_path / "original.txt"
    original.write_text("Hello, World!")

    # Create symlink
    link = tmp_path / "link.txt"
    link.symlink_to(original)

    result = analyzer.analyze_file(link)
    assert result is not None
    assert result.path == link
    assert result.has_signature()


def test_symlink_to_binary_file(tmp_path: Path) -> None:
    """Test analyzing a symlink pointing to a binary file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())

    # Create binary file
    binary = tmp_path / "binary.dat"
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
