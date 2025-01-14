"""Command-line interface for ndetect."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from ndetect.logging import setup_logging
from ndetect.text_detection import scan_paths

__all__ = ["parse_args", "scan_paths"]

logger = logging.getLogger(__name__)

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
        "--num-perm",
        type=int,
        default=128,
        help="Number of permutations for MinHash (default: 128)",
    )
    parser.add_argument(
        "--shingle-size",
        type=int,
        default=5,
        help="Size of shingles for text comparison (default: 5)",
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

def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parsed_args = parse_args(args)
    
    # Setup logging
    setup_logging(parsed_args.log_file, parsed_args.verbose)
    
    logger.info("Starting ndetect in %s mode", parsed_args.mode)
    logger.info("Scanning paths: %s", parsed_args.paths)
    logger.debug("Using similarity threshold: %f", parsed_args.threshold)
    logger.debug("MinHash config: num_perm=%d, shingle_size=%d", 
                parsed_args.num_perm, parsed_args.shingle_size)
    
    # Scan paths and collect text files
    text_files = scan_paths(
        parsed_args.paths,
        min_printable_ratio=parsed_args.min_printable_ratio,
        num_perm=parsed_args.num_perm,
        shingle_size=parsed_args.shingle_size
    )
    
    if not text_files:
        logger.warning("No text files found in the specified paths")
        return 1
    
    logger.info("Found %d text files", len(text_files))
    
    # TODO: Implement MinHash signature generation and similarity detection
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 