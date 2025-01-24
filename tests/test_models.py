from datetime import datetime
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from ndetect.models import TextFile


def test_textfile_from_path(create_text_file: Callable[[str, str], TextFile]) -> None:
    """Test TextFile creation from path."""
    text_file = create_text_file("test.txt", "Hello, World!")

    # Check basic properties
    assert text_file.size == len("Hello, World!")
    assert isinstance(text_file.modified_time, datetime)
    assert isinstance(text_file.created_time, datetime)
    assert text_file.extension == ".txt"
    assert text_file.name == "test.txt"
    assert text_file.has_signature()


def test_textfile_str_representation(
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    """Test string representation of TextFile."""
    text_file = create_text_file("test.txt", "Hello")
    str_repr = str(text_file)
    assert text_file.name in str_repr
    assert "bytes" in str_repr


def test_compute_signature_uses_cached_content(tmp_path: Path) -> None:
    """Test that compute_signature uses cached content for small files."""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"
    test_file.write_text(content)

    text_file = TextFile.from_path(test_file, compute_minhash=False)

    # Access content to cache it
    _ = text_file.content

    # Mock read_chunk to verify it's not called
    with patch.object(text_file, "read_chunk") as mock_read:
        text_file.compute_signature()
        mock_read.assert_not_called()
