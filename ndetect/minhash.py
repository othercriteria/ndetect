"""MinHash implementation for near-duplicate detection."""

from pathlib import Path
import numpy as np
from datasketch import MinHash

def create_minhash(content: str, num_perm: int = 128) -> MinHash:
    """
    Create a MinHash signature from text content.
    
    Args:
        content: Text content to hash
        num_perm: Number of permutations for MinHash (default: 128)
        
    Returns:
        MinHash object with the content's signature
    """
    minhash = MinHash(num_perm=num_perm)
    
    # Split content into words and add to MinHash
    words = content.split()
    for word in words:
        minhash.update(word.encode('utf-8'))
    
    return minhash

def compute_signature(file_path: Path, num_perm: int = 128) -> bytes | None:
    """
    Compute MinHash signature for a text file.
    
    Args:
        file_path: Path to the text file
        num_perm: Number of permutations for MinHash
        
    Returns:
        Bytes containing the MinHash signature, or None if file cannot be read
    """
    try:
        with file_path.open('r', encoding='utf-8') as f:
            content = f.read()
        
        minhash = create_minhash(content, num_perm)
        return bytes(minhash.digest().tobytes())
        
    except (IOError, OSError, UnicodeDecodeError):
        return None

def similarity(sig1: bytes, sig2: bytes, num_perm: int = 128) -> float:
    """
    Calculate Jaccard similarity between two MinHash signatures.
    
    Args:
        sig1: First MinHash signature
        sig2: Second MinHash signature
        num_perm: Number of permutations used in MinHash
        
    Returns:
        Estimated Jaccard similarity between the two signatures
    """
    # Create new MinHash objects
    mh1 = MinHash(num_perm=num_perm)
    mh2 = MinHash(num_perm=num_perm)
    
    # Convert bytes back to numpy arrays
    arr1 = np.frombuffer(sig1, dtype=np.uint64)
    arr2 = np.frombuffer(sig2, dtype=np.uint64)
    
    # Update the MinHash objects with the raw hash values
    for h in arr1:
        mh1.update(h.tobytes())
    for h in arr2:
        mh2.update(h.tobytes())
    
    return float(mh1.jaccard(mh2)) 
