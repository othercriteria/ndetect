from datetime import datetime
from pathlib import Path
from ndetect.models import TextFile

def test_textfile_from_path(tmp_path: Path) -> None:
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")
    
    # Create TextFile instance without computing MinHash
    text_file = TextFile.from_path(test_file, compute_minhash=False)
    
    # Check basic properties
    assert text_file.path == test_file
    assert text_file.size == len("Hello, World!")
    assert isinstance(text_file.modified_time, datetime)
    assert isinstance(text_file.created_time, datetime)
    assert text_file.extension == ".txt"
    assert text_file.name == "test.txt"
    assert text_file.parent == tmp_path
    assert not text_file.has_signature()

def test_textfile_str_representation(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")
    text_file = TextFile.from_path(test_file)
    str_repr = str(text_file)
    assert str(test_file) in str_repr
    assert "bytes" in str_repr 