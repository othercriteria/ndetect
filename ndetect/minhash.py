"""MinHash implementation for near-duplicate detection."""

from pathlib import Path
from typing import Optional

from datasketch import MinHash

from .models import TextFile


def compute_signature(
    path: Path,
    num_perm: int = 128,
    shingle_size: int = 5,
) -> Optional[MinHash]:
    """Compute MinHash signature for a file path."""
    try:
        file = TextFile.from_path(path, compute_minhash=False)
        return file.compute_signature(num_perm=num_perm, shingle_size=shingle_size)
    except Exception:
        return None


def similarity(sig1: MinHash, sig2: MinHash) -> float:
    """Calculate Jaccard similarity between two MinHash signatures."""
    return sig1.jaccard(sig2)
