"""Core MinHash signature computation functionality."""

from datasketch import MinHash


def compute_minhash_from_chunks(
    chunks: list[bytes],
    num_perm: int = 128,
    shingle_size: int = 5,
) -> MinHash:
    """
    Compute MinHash signature from a list of byte chunks.

    Args:
        chunks: List of byte chunks to process
        num_perm: Number of permutations for MinHash
        shingle_size: Size of shingles for text comparison

    Returns:
        MinHash signature
    """
    minhash = MinHash(num_perm=num_perm)

    # Process file in chunks to avoid memory issues
    buffer = ""
    for chunk in chunks:
        text = chunk.decode("utf-8", errors="replace")
        buffer += text

        # Process complete shingles from buffer
        while len(buffer) >= shingle_size:
            shingle = buffer[:shingle_size].lower()
            minhash.update(shingle.encode("utf-8"))
            buffer = buffer[1:]  # Slide window by 1

    # Process remaining buffer if any
    while len(buffer) >= shingle_size:
        shingle = buffer[:shingle_size].lower()
        minhash.update(shingle.encode("utf-8"))
        buffer = buffer[1:]

    return minhash
