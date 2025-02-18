"""Tests for file analysis functionality."""

from pathlib import Path

from ndetect.analysis import FileAnalyzer
from ndetect.models import FileAnalyzerConfig


def test_file_analyzer_with_text_file(tmp_path: Path) -> None:
    config = FileAnalyzerConfig()
    analyzer = FileAnalyzer(config)

    # Create a test text file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    result = analyzer.analyze_file(test_file)
    assert result is not None
    assert result.path == test_file
    assert result.has_signature()


def test_file_analyzer_with_binary_file(tmp_path: Path) -> None:
    config = FileAnalyzerConfig()
    analyzer = FileAnalyzer(config)

    # Create a test binary file
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(bytes([0x00, 0x01, 0x02, 0x03]))

    result = analyzer.analyze_file(test_file)
    assert result is None


def test_file_analyzer_with_custom_config(tmp_path: Path) -> None:
    config = FileAnalyzerConfig(
        min_printable_ratio=0.5,
        allowed_extensions={".xyz"},
        num_perm=256,
        shingle_size=3,
    )
    analyzer = FileAnalyzer(config)

    # Create a test file with custom extension
    test_file = tmp_path / "test.xyz"
    test_file.write_text("Hello\x00World")  # 50% printable

    result = analyzer.analyze_file(test_file)
    assert result is not None
    assert result.has_signature()


def test_file_analyzer_with_deep_symlinks(tmp_path: Path) -> None:
    """Test analyzer with deep symlink chains."""
    # Create a chain that exceeds default depth but within custom depth
    original = tmp_path / "original.txt"
    original.write_text("Hello, World!")

    current = original
    for i in range(12):  # Create chain of 12 symlinks (exceeds default 10)
        link = tmp_path / f"link{i}.txt"
        link.symlink_to(current)
        current = link

    # Should fail with default config
    default_analyzer = FileAnalyzer(FileAnalyzerConfig())
    assert default_analyzer.analyze_file(current) is None

    # Should succeed with higher max_symlink_depth
    custom_analyzer = FileAnalyzer(FileAnalyzerConfig(max_symlink_depth=15))
    result = custom_analyzer.analyze_file(current)
    assert result is not None
    assert result.path == current
