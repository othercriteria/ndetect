"""Tests for TextFile model."""

from datetime import datetime
from pathlib import Path
from typing import Callable

import pytest

from ndetect.exceptions import FileOperationError
from ndetect.models import TextFile


def test_content_property_basic(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test basic content property functionality."""
    test_content = "test content\nline 2"
    file = create_text_file("test.txt", test_content)

    assert file.content == test_content
    # Test caching - content should be the same on second read
    assert file.content == test_content


def test_content_property_size_limit(tmp_path: Path) -> None:
    """Test content property respects size limit."""
    file_path = tmp_path / "large.txt"
    # Create a 0-byte file but fake the size
    file_path.touch()

    text_file = TextFile(
        path=file_path,
        size=1024 * 1024 + 1,  # Pretend it's just over 1MB
        modified_time=datetime.now(),
        created_time=datetime.now(),
    )

    with pytest.raises(FileOperationError) as exc_info:
        _ = text_file.content
    assert "File too large" in str(exc_info.value)
    assert "1,048,577 bytes" in str(exc_info.value)


def test_content_property_encoding_errors(tmp_path: Path) -> None:
    """Test content property handles encoding errors gracefully."""
    # Create a file with invalid UTF-8 bytes
    file_path = tmp_path / "bad_encoding.txt"
    with open(file_path, "wb") as f:
        f.write(b"Hello \xff\xfe World")

    text_file = TextFile.from_path(file_path)
    content = text_file.content

    assert "Hello" in content
    assert "World" in content
    # The invalid bytes should be replaced with the Unicode replacement character
    assert "�" in content


def test_content_property_invalidation(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test content cache invalidation."""
    file = create_text_file("test.txt", "initial content")

    # First read caches content
    assert file.content == "initial content"

    # Update file content on disk
    file.path.write_text("new content")

    # Should still return cached content
    assert file.content == "initial content"

    # After invalidation, should read new content
    file.invalidate_content()
    assert file.content == "new content"


def test_content_property_missing_file(tmp_path: Path) -> None:
    """Test content property handles missing files."""
    file_path = tmp_path / "nonexistent.txt"
    text_file = TextFile(
        path=file_path,
        size=0,
        modified_time=datetime.fromtimestamp(0),
        created_time=datetime.fromtimestamp(0),
    )

    with pytest.raises(FileOperationError) as exc_info:
        _ = text_file.content
    assert "Failed to read file" in str(exc_info.value)


def test_read_chunk_streaming(create_text_file: Callable[[str, str], TextFile]) -> None:
    """Test streaming read functionality."""
    content = "line1\n" * 1000  # Create multi-chunk content
    file = create_text_file("test.txt", content)

    chunks = list(file.read_chunk(chunk_size=100))  # Small chunk size for testing

    # Verify chunks
    assert len(chunks) > 1  # Should have multiple chunks
    reconstructed = b"".join(chunks).decode("utf-8")
    assert reconstructed == content


def test_is_valid_text_with_cached_content(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test text validation using cached content."""
    # Create small file that will be cached
    file = create_text_file("test.txt", "Hello World!")

    # Access content to cache it
    _ = file.content

    # Validate text
    assert file.is_valid_text()

    # Should work with non-printable characters too
    file = create_text_file("test2.txt", "Hello\nWorld!")
    _ = file.content
    assert file.is_valid_text()


def test_is_valid_text_streaming(tmp_path: Path) -> None:
    """Test text validation using streaming for larger files."""
    file_path = tmp_path / "test.txt"

    # Create file with mix of printable and non-printable characters
    content = bytes([x % 256 for x in range(1000)])  # Creates bytes 0-255 repeating
    file_path.write_bytes(content)

    text_file = TextFile.from_path(file_path, compute_minhash=False)

    # Should fail validation due to too many non-printable characters
    assert not text_file.is_valid_text(min_printable_ratio=0.8)

    # Create file with mostly printable ASCII
    printable_content = (
        b"".join(bytes([x]) for x in range(32, 127)) * 10
    )  # Repeating printable ASCII
    file_path.write_bytes(printable_content)

    text_file = TextFile.from_path(file_path, compute_minhash=False)
    assert text_file.is_valid_text(min_printable_ratio=0.8)


def test_is_valid_text_empty_file(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test text validation with empty file."""
    file = create_text_file("empty.txt", "")
    assert file.is_valid_text()


def test_is_valid_text_unicode(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test text validation with Unicode content."""
    # Mix of ASCII, Unicode, and whitespace
    content = "Hello 世界\n¡Hola!\nПривет!"
    file = create_text_file("unicode.txt", content)
    assert file.is_valid_text()


def test_read_chunk_nonexistent_file(tmp_path: Path) -> None:
    """Test streaming from nonexistent file."""
    file_path = tmp_path / "nonexistent.txt"
    text_file = TextFile(
        path=file_path,
        size=0,
        modified_time=datetime.fromtimestamp(0),
        created_time=datetime.fromtimestamp(0),
    )

    with pytest.raises(FileOperationError):
        next(text_file.read_chunk())


def test_is_valid_text_empty_file_exists(tmp_path: Path) -> None:
    """Test text validation with empty file that exists on disk."""
    file_path = tmp_path / "empty.txt"
    file_path.touch()  # Create empty file

    text_file = TextFile.from_path(file_path, compute_minhash=False)
    assert text_file.is_valid_text()
