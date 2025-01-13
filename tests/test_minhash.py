from pathlib import Path
from ndetect.minhash import create_minhash, compute_signature, similarity

def test_create_minhash() -> None:
    content1 = "hello world"
    content2 = "hello world"
    content3 = "different text"
    
    mh1 = create_minhash(content1)
    mh2 = create_minhash(content2)
    mh3 = create_minhash(content3)
    
    # Same content should have same signature
    assert (mh1.digest() == mh2.digest()).all()
    # Different content should have different signature
    assert not (mh1.digest() == mh3.digest()).all()

def test_compute_signature(tmp_path: Path) -> None:
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    
    file1.write_text("hello world")
    file2.write_text("hello world")
    
    sig1 = compute_signature(file1)
    sig2 = compute_signature(file2)
    
    assert sig1 is not None
    assert sig2 is not None
    assert sig1 == sig2  # Now comparing bytes objects

def test_compute_signature_invalid_file(tmp_path: Path) -> None:
    file_path = tmp_path / "nonexistent.txt"
    assert compute_signature(file_path) is None

def test_similarity() -> None:
    content1 = "hello world"
    content2 = "hello world"
    content3 = "completely different text"
    
    mh1 = create_minhash(content1)
    mh2 = create_minhash(content2)
    mh3 = create_minhash(content3)
    
    sig1 = mh1.digest().tobytes()
    sig2 = mh2.digest().tobytes()
    sig3 = mh3.digest().tobytes()
    
    # Same content should have similarity 1.0
    assert similarity(sig1, sig2) == 1.0
    # Different content should have lower similarity
    assert similarity(sig1, sig3) < 1.0  # Less strict assertion 