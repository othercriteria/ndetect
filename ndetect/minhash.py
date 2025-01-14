"""MinHash implementation for near-duplicate detection."""

from pathlib import Path
import numpy as np
from datasketch import MinHash
from typing import Optional, Iterator
from concurrent.futures import ThreadPoolExecutor

def _chunk_text(text: str, chunk_size: int = 1024 * 1024) -> Iterator[str]:
    """Split text into chunks for parallel processing."""
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

def _process_chunk(args: tuple[str, int]) -> set[str]:
    """Process a single chunk of text to generate shingles."""
    chunk, k = args
    return {chunk[i:i+k] for i in range(len(chunk) - k + 1)}

def create_shingles(text: str, k: int = 5, chunk_size: int = 1024 * 1024) -> set[str]:
    """Create k-shingles from text content using parallel processing for large files."""
    # Normalize text
    text = ' '.join(text.lower().split())
    
    # For small files, process directly
    if len(text) <= chunk_size:
        return {text[i:i+k] for i in range(len(text) - k + 1)}
    
    # For large files, process in parallel
    chunks = list(_chunk_text(text, chunk_size))
    shingles: set[str] = set()
    
    with ThreadPoolExecutor() as executor:
        # Process chunks in parallel
        chunk_results = list(executor.map(
            _process_chunk,
            [(chunk, k) for chunk in chunks]
        ))
        
        # Combine results
        for result in chunk_results:
            shingles.update(result)
        
        # Handle shingles that cross chunk boundaries
        for i in range(len(chunks) - 1):
            boundary_text = chunks[i][-k:] + chunks[i+1][:k]
            boundary_shingles = {
                boundary_text[j:j+k]
                for j in range(len(boundary_text) - k + 1)
            }
            shingles.update(boundary_shingles)
    
    return shingles

def create_minhash(content: str, num_perm: int = 128, shingle_size: int = 5) -> MinHash:
    """
    Create a MinHash signature from text content using shingling.
    
    Args:
        content: Text content to hash
        num_perm: Number of permutations for MinHash (default: 128)
        shingle_size: Size of shingles to use (default: 5)
        
    Returns:
        MinHash object with the content's signature
    """
    minhash = MinHash(num_perm=num_perm)
    
    # Generate shingles and add to MinHash
    shingles = create_shingles(content, k=shingle_size)
    for shingle in shingles:
        minhash.update(shingle.encode('utf-8'))
    
    return minhash

def compute_signature(path: Path, num_perm: int = 128, shingle_size: int = 5) -> Optional[MinHash]:
    """
    Compute MinHash signature for a text file.
    
    Args:
        path: Path to the text file
        num_perm: Number of permutations for MinHash
        shingle_size: Size of shingles to use
        
    Returns:
        MinHash object representing the file's signature, or None if file cannot be read
    """
    try:
        minhash = MinHash(num_perm=num_perm)
        
        with path.open('r', encoding='utf-8') as f:
            content = f.read()
            
        # Generate k-shingles
        shingles = {
            content[i:i + shingle_size]
            for i in range(len(content) - shingle_size + 1)
        }
        
        # Update MinHash with shingles
        for shingle in shingles:
            minhash.update(shingle.encode('utf-8'))
            
        return minhash
        
    except (IOError, OSError):
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
