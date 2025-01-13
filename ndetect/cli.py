import argparse
import logging
import sys
from typing import List, Optional
from pathlib import Path

from ndetect.text_detection import is_text_file
from ndetect.logging import setup_logging
from ndetect.models import TextFile

logger = logging.getLogger("ndetect")

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detect and manage near-duplicate text files using MinHash"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Paths to files or directories to scan for duplicates",
    )
    parser.add_argument(
        "--mode",
        choices=["interactive", "non-interactive"],
        default="interactive",
        help="Operation mode (default: interactive)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Similarity threshold (default: 0.85)",
    )
    parser.add_argument(
        "--min-printable-ratio",
        type=float,
        default=0.8,
        help="Minimum ratio of printable characters for text detection (default: 0.8)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to log file (if not specified, only log to console)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    return parser.parse_args(args)

def scan_paths(paths: List[str], min_printable_ratio: float) -> List[TextFile]:
    """
    Scan paths and return a list of TextFile instances for valid text files.
    
    Args:
        paths: List of paths to scan
        min_printable_ratio: Minimum ratio of printable characters for text detection
        
    Returns:
        List of TextFile instances for valid text files
    """
    text_files: List[TextFile] = []
    
    for path in paths:
        path_obj = Path(path)
        if path_obj.is_dir():
            logger.info("Scanning directory: %s", path)
            for file in path_obj.rglob("*"):
                if not file.is_file():
                    continue
                if not is_text_file(file, min_printable_ratio=min_printable_ratio):
                    logger.debug("Skipping file: %s (not a text file)", file)
                    continue
                text_file = TextFile.from_path(file)
                text_files.append(text_file)
                logger.debug("Found text file: %s", text_file)
        elif path_obj.is_file():
            logger.info("Scanning file: %s", path)
            if is_text_file(path_obj, min_printable_ratio=min_printable_ratio):
                text_file = TextFile.from_path(path_obj)
                text_files.append(text_file)
                logger.debug("Found text file: %s", text_file)
            else:
                logger.debug("Skipping file: %s (not a text file)", path)
    
    return text_files

def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parsed_args = parse_args(args)
    
    # Setup logging
    setup_logging(parsed_args.log_file, parsed_args.verbose)
    
    logger.info("Starting ndetect in %s mode", parsed_args.mode)
    logger.info("Scanning paths: %s", parsed_args.paths)
    logger.debug("Using similarity threshold: %f", parsed_args.threshold)
    
    # Scan paths and collect text files
    text_files = scan_paths(parsed_args.paths, parsed_args.min_printable_ratio)
    
    if not text_files:
        logger.warning("No text files found in the specified paths")
        return 1
    
    logger.info("Found %d text files", len(text_files))
    
    # TODO: Implement MinHash signature generation and similarity detection
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 