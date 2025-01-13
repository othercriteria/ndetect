import argparse
import sys
from typing import List, Optional
from pathlib import Path
from ndetect.text_detection import is_text_file


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
    parser.add_argument(
        "--min-printable-ratio",
        type=float,
        default=0.8,
        help="Minimum ratio of printable characters for text detection (default: 0.8)",
    )
    
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed_args = parse_args(args)
    print(f"Starting ndetect in {parsed_args.mode} mode")
    print(f"Scanning paths: {parsed_args.paths}")
    print(f"Using similarity threshold: {parsed_args.threshold}")

    for path in parsed_args.paths:
        path_obj = Path(path)
        if path_obj.is_dir():
            print(f"Scanning directory: {path}")
            for file in path_obj.rglob("*"):
                if not file.is_file():
                    continue
                if not is_text_file(file, min_printable_ratio=parsed_args.min_printable_ratio):
                    print(f"Skipping file: {file} (not a text file)")
                    continue
                # Process text file here
        else:
            print(f"Scanning file: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main()) 