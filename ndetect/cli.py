import argparse
import sys
from typing import List, Optional


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
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
    
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed_args = parse_args(args)
    print(f"Starting ndetect in {parsed_args.mode} mode")
    print(f"Scanning paths: {parsed_args.paths}")
    print(f"Using similarity threshold: {parsed_args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 