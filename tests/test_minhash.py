from pathlib import Path
from ndetect.minhash import create_minhash, compute_signature, similarity, create_shingles

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

def test_create_shingles() -> None:
    text = "hello world"
    shingles = create_shingles(text, k=3)
    expected = {"hel", "ell", "llo", "lo ", "o w", " wo", "wor", "orl", "rld"}
    assert shingles == expected

def test_create_shingles_normalized() -> None:
    text1 = "Hello  World"
    text2 = "hello world"
    shingles1 = create_shingles(text1, k=3)
    shingles2 = create_shingles(text2, k=3)
    assert shingles1 == shingles2

def test_similar_text_higher_similarity() -> None:
    text1 = "hello world how are you"
    text2 = "hello world how are they"  # Only last word different
    
    mh1 = create_minhash(text1)
    mh2 = create_minhash(text2)
    
    sig1 = mh1.digest().tobytes()
    sig2 = mh2.digest().tobytes()
    
    similarity_score = similarity(sig1, sig2)
    assert similarity_score > 0.7  # High similarity expected 