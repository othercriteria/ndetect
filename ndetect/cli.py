"""Command-line interface for ndetect."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console

from ndetect.logging import setup_logging
from ndetect.text_detection import scan_paths
from ndetect.ui import InteractiveUI
from ndetect.similarity import SimilarityGraph
from ndetect.models import TextFile

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
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Maximum number of worker processes for parallel processing",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Chunk size in bytes for processing large files (default: 1MB)",
    )
    
    return parser.parse_args(args)

def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    args = parse_args(argv if argv is not None else None)
    setup_logging(args.log_file, args.verbose)
    
    ui = InteractiveUI()
    console = Console()  # For system/error messages
    
    try:
        # Show scanning progress
        ui.show_scan_progress(args.paths)
        text_files = scan_paths(
            args.paths,
            min_printable_ratio=args.min_printable_ratio,
            num_perm=args.num_perm,
            shingle_size=args.shingle_size,
        )
        
        if not text_files:
            console.print("[yellow]No text files found in the specified paths.[/yellow]")
            return 0
            
        console.print(f"\nFound [green]{len(text_files)}[/green] text files.")
        
        if args.mode == "interactive":
            return handle_interactive_mode(ui, text_files, args.threshold)
        else:
            return handle_non_interactive_mode(console, text_files, args.threshold)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if args.verbose:
            console.print_exception()
        return 1

def handle_interactive_mode(ui: InteractiveUI, text_files: List[TextFile], threshold: float) -> int:
    """Handle interactive mode with rich UI."""
    # Build similarity graph
    graph = SimilarityGraph(threshold=threshold)
    graph.add_files(text_files)
    
    while True:
        groups = graph.get_groups()
        if not groups:
            ui.show_success("No more duplicate groups found.")
            return 0
            
        for group in groups:
            ui.display_group(group.id, group.files, group.similarity)
            action = ui.prompt_action()
            
            if action == "q":
                return 0
            elif action == "s":
                continue
            elif action == "k":
                continue  # Skip to next group
            elif action == "d":
                files = ui.select_files(group.files, "Select files to delete")
                if files and ui.confirm_action("delete", files):
                    for file in files:
                        file.unlink()
                    graph.remove_files(files)
            elif action == "m":
                # TODO: Implement move to holding directory
                ui.show_error("Move to holding not yet implemented")
            elif action == "i":
                # TODO: Show detailed file information
                ui.show_error("Detailed info not yet implemented")
    
    return 0

def handle_non_interactive_mode(console: Console, text_files: List['TextFile'], threshold: float) -> int:
    """Handle non-interactive mode with basic output."""
    # TODO: Implement non-interactive mode
    console.print("[yellow]Non-interactive mode not yet implemented[/yellow]")
    return 1

if __name__ == "__main__":
    sys.exit(main()) 