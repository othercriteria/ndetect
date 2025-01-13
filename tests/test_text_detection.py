from pathlib import Path
from ndetect.text_detection import is_text_file


def test_is_text_file_with_invalid_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "test.bin"
    file_path.write_text("Hello, World!")
    assert not is_text_file(file_path)


def test_is_text_file_with_valid_text(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    assert is_text_file(file_path)


def test_is_text_file_with_binary_content(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"
    with file_path.open("wb") as f:
        f.write(bytes([0x00, 0x01, 0x02, 0x03]))
    assert not is_text_file(file_path)


def test_is_text_file_with_custom_extensions(tmp_path: Path) -> None:
    file_path = tmp_path / "test.xyz"
    file_path.write_text("Hello, World!")
    assert not is_text_file(file_path)
    assert is_text_file(file_path, allowed_extensions={".xyz"})


def test_is_text_file_with_low_printable_ratio(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"
    # Create a string with >50% (but <80%) printable characters
    content = "Hello\x00\x00World\x00!"
    file_path.write_bytes(content.encode("utf-8"))
    assert not is_text_file(file_path)
    assert is_text_file(file_path, min_printable_ratio=0.5) 