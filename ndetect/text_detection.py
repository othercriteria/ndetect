"""Text file detection and scanning functionality."""

from pathlib import Path
from typing import List, Optional, Set

from ndetect.analysis import FileAnalyzer, FileAnalyzerConfig
from ndetect.models import TextFile

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
    config = FileAnalyzerConfig(
        min_printable_ratio=min_printable_ratio,
        num_perm=num_perm,
        shingle_size=shingle_size,
        allowed_extensions=allowed_extensions
    )
    analyzer = FileAnalyzer(config)
    text_files: List[TextFile] = []
    
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            if result := analyzer.analyze_file(path):
                text_files.append(result)
        elif path.is_dir():
            for file_path in path.rglob("*"):
                if result := analyzer.analyze_file(file_path):
                    text_files.append(result)
    
    return text_files 