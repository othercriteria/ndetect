from pathlib import Path
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