"""MinHash implementation for near-duplicate detection."""

from pathlib import Path
from typing import Optional, Set

import numpy as np
from datasketch import MinHash

from ndetect.types import MinHashSignature, SimilarityScore


def create_shingles(text: str, k: int = 5) -> Set[str]:
    """
    Create k-shingles from text.

    Args:
        text: Input text
        k: Size of each shingle

    Returns:
        Set of k-shingles
    """
    # Normalize text: lowercase and collapse whitespace
    text = " ".join(text.lower().split())
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def create_minhash(text: str, num_perm: int = 128, shingle_size: int = 5) -> MinHash:
    """
    Create MinHash signature from text.

    Args:
        text: Input text
        num_perm: Number of permutations to use
        shingle_size: Size of shingles for text splitting

    Returns:
        MinHash object
    """
    minhash = MinHash(num_perm=num_perm)
    # Add each shingle to the MinHash
    for shingle in create_shingles(text, k=shingle_size):
        minhash.update(shingle.encode("utf-8"))
    return minhash


def compute_signature(
    file_path: Path, num_perm: int = 128, shingle_size: int = 5
) -> Optional[MinHash]:
    """
    Compute MinHash signature for a file using streaming reads.

    Args:
        file_path: Path to the file
        num_perm: Number of permutations to use
        shingle_size: Size of shingles for text splitting

    Returns:
        MinHash object, or None if file cannot be read
    """
    try:
        minhash = MinHash(num_perm=num_perm)
        buffer = ""

        with open(file_path, "r", encoding="utf-8") as f:
            while True:
                chunk = f.read(8192)  # Read 8KB at a time
                if not chunk:
                    # Process remaining buffer
                    if buffer:
                        normalized = " ".join(buffer.lower().split())
                        for i in range(len(normalized) - shingle_size + 1):
                            shingle = normalized[i : i + shingle_size]
                            minhash.update(shingle.encode("utf-8"))
                    break

                buffer += chunk
                # Process complete shingles from buffer
                while len(buffer) >= shingle_size * 2:
                    # Normalize the processable portion
                    normalized = " ".join(buffer[: shingle_size * 2].lower().split())
                    for i in range(len(normalized) - shingle_size + 1):
                        shingle = normalized[i : i + shingle_size]
                        minhash.update(shingle.encode("utf-8"))
                    # Keep the remainder that might contain incomplete shingles
                    buffer = buffer[shingle_size:]

        return minhash
    except (IOError, UnicodeDecodeError):
        return None


def similarity(
    sig1: MinHashSignature, sig2: MinHashSignature, num_perm: int = 128
) -> SimilarityScore:
    """
    Calculate Jaccard similarity between two MinHash signatures.

    Args:
        sig1: First MinHash signature
        sig2: Second MinHash signature
        num_perm: Number of permutations used in MinHash

    Returns:
        Estimated Jaccard similarity between the two signatures
    """
    # Convert bytes back to numpy arrays
    arr1 = np.frombuffer(sig1, dtype=np.uint64)
    arr2 = np.frombuffer(sig2, dtype=np.uint64)

    # Calculate Jaccard similarity directly from the arrays
    # Jaccard similarity = number of equal elements / total number of elements
    equal_count = np.sum(arr1 == arr2)
    return SimilarityScore(float(equal_count) / len(arr1))
