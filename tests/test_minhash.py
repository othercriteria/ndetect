from pathlib import Path

from ndetect.minhash import (
    compute_signature,
)
from ndetect.signatures import compute_minhash_from_chunks


def test_create_minhash() -> None:
    """Test MinHash creation with different inputs."""
    text1 = b"This is a test document"
    text2 = b"This is another test document"

    sig1 = compute_minhash_from_chunks([text1])
    sig2 = compute_minhash_from_chunks([text2])

    # Similar texts should have higher similarity
    assert sig1.jaccard(sig2) > 0.5


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
    # Compare MinHash objects directly since compute_signature now returns MinHash
    assert (sig1.digest() == sig2.digest()).all()


def test_compute_signature_invalid_file(tmp_path: Path) -> None:
    file_path = tmp_path / "nonexistent.txt"
    assert compute_signature(file_path) is None


def test_similarity() -> None:
    """Test similarity calculation between two texts."""
    text1 = b"This is a test document"
    text2 = b"This is another test document"

    sig1 = compute_minhash_from_chunks([text1])
    sig2 = compute_minhash_from_chunks([text2])

    # Similar texts should have higher similarity
    assert sig1.jaccard(sig2) > 0.5


def test_similar_text_higher_similarity() -> None:
    """Test that more similar texts have higher similarity scores."""
    base = b"This is a test document about similarity measurement"
    similar = b"This is a test document about similarity testing"
    different = b"Something completely different here"

    base_sig = compute_minhash_from_chunks([base])
    similar_sig = compute_minhash_from_chunks([similar])
    different_sig = compute_minhash_from_chunks([different])

    similar_score = base_sig.jaccard(similar_sig)
    different_score = base_sig.jaccard(different_sig)

    assert similar_score > different_score


def test_case_insensitive_similarity() -> None:
    """Test that case differences don't affect similarity."""
    text1 = b"Hello World"
    text2 = b"hello world"

    sig1 = compute_minhash_from_chunks([text1])
    sig2 = compute_minhash_from_chunks([text2])

    assert sig1.jaccard(sig2) == 1.0
