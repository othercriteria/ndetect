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
        help="Maximum number of worker processes (default: number of CPU cores)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Chunk size in bytes for processing large files (default: 1MB)",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=100,
        help="Maximum characters in file preview (default: 100)",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=3,
        help="Maximum lines in file preview (default: 3)",
    )
    
    return parser.parse_args(args)

def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    args = parse_args(argv if argv is not None else None)
    setup_logging(args.log_file, args.verbose)
    
    # Create console once
    console = Console()
    
    # Create UI with preview configuration
    ui = InteractiveUI(
        console=console,
        preview_config={
            'max_chars': args.preview_chars,
            'max_lines': args.preview_lines,
            'truncation_marker': '...'
        }
    )
    
    try:
        text_files = scan_paths(args.paths, min_printable_ratio=args.min_printable_ratio, num_perm=args.num_perm, shingle_size=args.shingle_size)
        if not text_files:
            console.print("[red]No valid text files found.[/red]")
            return 1
            
        console.print(f"Found {len(text_files)} text files.")
        
        if args.mode == "interactive":
            return handle_interactive_mode(ui, text_files, args.threshold)
        else:
            console.print("[red]Unknown mode specified.[/red]")
            return 1
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
                # Get pairwise similarities for the group
                similarities = graph.get_group_similarities(group.files)
                ui.show_detailed_info(group.files, similarities)
                # Wait for user to press enter before continuing
                ui.console.input("\nPress Enter to continue...")
    
    return 0

def handle_non_interactive_mode(console: Console, text_files: List['TextFile'], threshold: float) -> int:
    """Handle non-interactive mode with basic output."""
    # TODO: Implement non-interactive mode
    console.print("[yellow]Non-interactive mode not yet implemented[/yellow]")
    return 1

if __name__ == "__main__":
    sys.exit(main()) 