from pathlib import Path

import pytest

from ndetect.analysis import FileAnalyzer, FileAnalyzerConfig


def test_file_analyzer_with_invalid_extension(tmp_path: Path) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.bin"
    file_path.write_text("Hello, World!")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_valid_text(tmp_path: Path) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    result = analyzer.analyze_file(file_path)
    assert result is not None


def test_file_analyzer_with_binary_content(tmp_path: Path) -> None:
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.txt"
    with file_path.open("wb") as f:
        f.write(bytes([0x00, 0x01, 0x02, 0x03]))
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_custom_extensions(tmp_path: Path) -> None:
    file_path = tmp_path / "test.xyz"
    file_path.write_text("Hello, World!")

    default_analyzer = FileAnalyzer(FileAnalyzerConfig())
    assert default_analyzer.analyze_file(file_path) is None

    custom_analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions={".xyz"}))
    assert custom_analyzer.analyze_file(file_path) is not None


def test_file_analyzer_with_low_printable_ratio(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"
    # Create a string with >50% (but <80%) printable characters
    content = "Hello\x00\x00World\x00!"
    file_path.write_bytes(content.encode("utf-8"))

    strict_analyzer = FileAnalyzer(FileAnalyzerConfig())
    assert strict_analyzer.analyze_file(file_path) is None

    lenient_analyzer = FileAnalyzer(FileAnalyzerConfig(min_printable_ratio=0.5))
    assert lenient_analyzer.analyze_file(file_path) is not None


def test_file_analyzer_empty_file(tmp_path: Path) -> None:
    """Test analyzer with empty file."""
    # Create config with .txt in allowed extensions
    analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions={".txt"}))
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")
    result = analyzer.analyze_file(file_path)
    assert result is not None
    assert result.size == 0


def test_file_analyzer_very_large_file(tmp_path: Path) -> None:
    """Test analyzer with file larger than read buffer."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "large.txt"
    # Create file larger than 8KB buffer
    content = "x" * 10000
    file_path.write_text(content)
    result = analyzer.analyze_file(file_path)
    assert result is not None
    assert result.size == 10000


def test_file_analyzer_with_unicode_content(tmp_path: Path) -> None:
    """Test analyzer with various Unicode characters."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "unicode.txt"
    # Mix of ASCII and Unicode characters
    content = "Hello, 世界! ñ č ß 🌍"
    file_path.write_text(content)
    result = analyzer.analyze_file(file_path)
    assert result is not None


def test_file_analyzer_with_null_bytes(tmp_path: Path) -> None:
    """Test analyzer with null bytes in content."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions={".txt"}))
    file_path = tmp_path / "test.txt"
    # Create content where null bytes make up >20% of the content
    content = "Hi\x00\x00\x00\x00\x00World"  # 5 nulls in 12 chars
    file_path.write_bytes(content.encode("utf-8"))
    result = analyzer.analyze_file(file_path)
    assert result is None


def test_file_analyzer_with_permission_error(tmp_path: Path) -> None:
    """Test analyzer with unreadable file."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "noperm.txt"
    file_path.write_text("test")
    file_path.chmod(0o000)  # Remove all permissions
    result = analyzer.analyze_file(file_path)
    assert result is None
    file_path.chmod(0o666)  # Restore permissions for cleanup


def test_file_analyzer_with_custom_printable_ratio(tmp_path: Path) -> None:
    """Test analyzer with different printable ratio thresholds."""
    # Create content where ~60% is printable (6 printable chars, 4 non-printable)
    content = "Hello\x00\x00\x00\x00W"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content.encode("utf-8"))

    # Test with different thresholds
    strict = FileAnalyzer(
        FileAnalyzerConfig(min_printable_ratio=0.8, allowed_extensions={".txt"})
    )
    lenient = FileAnalyzer(
        FileAnalyzerConfig(min_printable_ratio=0.5, allowed_extensions={".txt"})
    )

    assert strict.analyze_file(file_path) is None  # Should fail 80% threshold
    assert lenient.analyze_file(file_path) is not None  # Should pass 50% threshold


def test_file_analyzer_with_invalid_utf8(tmp_path: Path) -> None:
    """Test analyzer with invalid UTF-8 content."""
    analyzer = FileAnalyzer(FileAnalyzerConfig())
    file_path = tmp_path / "test.txt"
    # Write invalid UTF-8 bytes
    file_path.write_bytes(b"\xff\xfe\xfd")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_mixed_extensions(tmp_path: Path) -> None:
    """Test analyzer with mixed case extensions."""
    content = "Hello, World!"
    config = FileAnalyzerConfig(allowed_extensions={".txt", ".TXT"})
    analyzer = FileAnalyzer(config)

    # Test different case variations
    file1 = tmp_path / "test.txt"
    file2 = tmp_path / "test.TXT"
    file3 = tmp_path / "test.Txt"

    file1.write_text(content)
    file2.write_text(content)
    file3.write_text(content)

    assert analyzer.analyze_file(file1) is not None
    assert analyzer.analyze_file(file2) is not None
    assert analyzer.analyze_file(file3) is not None


def test_file_analyzer_with_empty_extensions_set(tmp_path: Path) -> None:
    """Test analyzer with empty allowed extensions set."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(allowed_extensions=set()))
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    assert analyzer.analyze_file(file_path) is None


def test_file_analyzer_with_symlink(tmp_path: Path) -> None:
    """Test analyzer with symbolic links."""
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


@pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0])
def test_file_analyzer_printable_ratio_bounds(tmp_path: Path, ratio: float) -> None:
    """Test analyzer with boundary values for printable ratio."""
    analyzer = FileAnalyzer(FileAnalyzerConfig(min_printable_ratio=ratio))
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    result = analyzer.analyze_file(file_path)
    assert (result is not None) == (ratio <= 1.0)
