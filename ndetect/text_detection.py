from pathlib import Path
from typing import List, Optional, Set

from ndetect.models import TextFile

SAMPLE_SIZE_BYTES = 8 * 1024  # 8KB

def is_text_file(
    file_path: Path,
    min_printable_ratio: float = 0.8,
    allowed_extensions: Optional[Set[str]] = None,
) -> bool:
    """
    Check if a file is likely to be a text file.

    Args:
        file_path: Path to the file to check
        min_printable_ratio: Minimum ratio of printable characters (default: 0.8)
        allowed_extensions: Set of allowed file extensions (default: {'.txt', '.md', '.log', '.csv'})

    Returns:
        bool: True if the file is likely to be a text file, False otherwise
    """
    if allowed_extensions is None:
        allowed_extensions = {".txt", ".md", ".log", ".csv"}

    # Check file extension
    if file_path.suffix.lower() not in allowed_extensions:
        return False

    try:
        # Try reading the first 8KB of the file
        with file_path.open("rb") as f:
            raw_bytes = f.read(SAMPLE_SIZE_BYTES)

        # Try decoding as UTF-8
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return False

        # Count printable characters
        printable_chars = sum(1 for c in content if c.isprintable() or c.isspace())
        ratio = printable_chars / len(content) if content else 0

        return ratio >= min_printable_ratio

    except (IOError, OSError):
        return False

def scan_paths(
    paths: List[str],
    min_printable_ratio: float = 0.8,
    num_perm: int = 128,
    shingle_size: int = 5,
    allowed_extensions: Optional[Set[str]] = None,
) -> List[TextFile]:
    """
    Scan paths and return a list of TextFile instances for valid text files.
    
    Args:
        paths: List of paths to scan
        min_printable_ratio: Minimum ratio of printable characters for text detection
        num_perm: Number of permutations for MinHash
        shingle_size: Size of shingles to use
        allowed_extensions: Set of allowed file extensions
        
    Returns:
        List of TextFile instances for valid text files
    """
    text_files: List[TextFile] = []
    
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            if is_text_file(path, min_printable_ratio, allowed_extensions):
                text_file = TextFile.from_path(
                    path,
                    compute_minhash=True,
                    num_perm=num_perm,
                    shingle_size=shingle_size
                )
                text_files.append(text_file)
        elif path.is_dir():
            for file_path in path.rglob("*"):
                if is_text_file(file_path, min_printable_ratio, allowed_extensions):
                    text_file = TextFile.from_path(
                        file_path,
                        compute_minhash=True,
                        num_perm=num_perm,
                        shingle_size=shingle_size
                    )
                    text_files.append(text_file)
    
    return text_files 