"""Command-line interface for ndetect."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from collections import defaultdict
import shutil

from ndetect.logging import setup_logging
from ndetect.text_detection import scan_paths
from ndetect.ui import InteractiveUI
from ndetect.similarity import SimilarityGraph
from ndetect.models import TextFile, MoveConfig, MoveOperation, PreviewConfig

__all__ = [
    'parse_args',
    'scan_paths',
    'prepare_moves',
    'execute_moves',
]

logger = logging.getLogger(__name__)

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detect and manage similar text files."
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
    parser.add_argument(
        "--holding-dir",
        type=Path,
        default=Path("holding"),
        help="Directory to move duplicate files to (default: ./holding)"
    )
    parser.add_argument(
        "--flat-holding",
        action="store_true",
        help="Don't preserve directory structure when moving files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    args = parse_args(argv if argv is not None else None)
    setup_logging(args.log_file, args.verbose)
    
    # Create console once
    console = Console()
    
    # Create UI with configurations
    move_config = MoveConfig(
        holding_dir=args.holding_dir,
        preserve_structure=not args.flat_holding,
        dry_run=args.dry_run
    )
    preview_config = PreviewConfig(
        max_chars=args.preview_chars,
        max_lines=args.preview_lines
    )
    ui = InteractiveUI(
        console=console,
        move_config=move_config,
        preview_config=preview_config
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
    # Build similarity graph with progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=ui.console,
    ) as progress:
        task = progress.add_task(
            "Building similarity graph...",
            total=len(text_files)
        )
        
        graph = SimilarityGraph(threshold=threshold)
        batch_size = 1000
        for i in range(0, len(text_files), batch_size):
            batch = text_files[i:i + batch_size]
            graph.add_files(batch)
            progress.advance(task, len(batch))
    
    while True:
        groups = graph.get_groups()
        if not groups:
            if ui.pending_moves:
                return handle_cleanup_phase(ui)
            ui.show_success("No more duplicate groups found.")
            return 0
            
        group = groups[0]
        while True:
            ui.display_group(group.id, group.files, group.similarity)
            action = ui.prompt_action()
            
            if action == "q":
                return 0
            elif action == "k":
                # Remove all edges in this group to prevent it from appearing again
                graph.remove_group(group.files)
                break
            elif action == "d":
                files = ui.select_files(group.files, "Select files to delete")
                if files and ui.confirm_action("delete", files):
                    for file in files:
                        file.unlink()
                    graph.remove_files(files)
                    # Check if we need to move to next group
                    groups = graph.get_groups()
                    if not groups or groups[0].files != group.files:
                        break
            elif action == "m":
                files = ui.select_files(group.files, "Select files to move")
                if files:
                    moves = prepare_moves(
                        files, 
                        ui.move_config.holding_dir,
                        preserve_structure=ui.move_config.preserve_structure,
                        group_id=group.id
                    )
                    ui.display_move_preview(moves)
                    if ui.confirm_action("move", files):
                        if not ui.move_config.dry_run:
                            execute_moves(moves)
                        graph.remove_files(files)
                        ui.pending_moves.extend(moves)
                        groups = graph.get_groups()
                        if not groups or groups[0].files != group.files:
                            break
            elif action == "i":
                # Get pairwise similarities for the group
                similarities = graph.get_group_similarities(group.files)
                ui.show_detailed_info(group.files, similarities)
                # Wait for user to press enter before continuing with same group
                ui.console.input("\nPress Enter to continue...")
    
    return 0

def handle_non_interactive_mode(console: Console, text_files: List['TextFile'], threshold: float) -> int:
    """Handle non-interactive mode with basic output."""
    # TODO: Implement non-interactive mode
    console.print("[yellow]Non-interactive mode not yet implemented[/yellow]")
    return 1

def handle_cleanup_phase(ui: InteractiveUI) -> int:
    """Handle final cleanup of moved files."""
    ui.console.print("\n[bold]Cleanup Phase[/bold]")
    
    if not ui.pending_moves:
        logger.info("No pending moves to clean up")
        return 0
        
    # Group moves by destination directory
    by_dest: dict[Path, list[MoveOperation]] = defaultdict(list)
    for move in ui.pending_moves:
        by_dest[move.destination.parent].append(move)
    
    logger.info(f"Cleaning up {len(ui.pending_moves)} moves across {len(by_dest)} directories")
    
    # Show summary
    ui.console.print(f"\nMoved {len(ui.pending_moves)} files to {len(by_dest)} directories:")
    for dest, moves in by_dest.items():
        ui.console.print(f"\n{dest}:")
        for move in moves:
            ui.console.print(f"  {move.source.name}")
            
    if ui.move_config.dry_run:
        logger.info("Dry run - no actual cleanup needed")
        ui.console.print("\n[yellow]DRY RUN - No files were actually moved[/yellow]")
        return 0
        
    # Offer to delete holding directory
    if ui.confirm_action("delete", [ui.move_config.holding_dir]):
        try:
            logger.info(f"Deleting holding directory: {ui.move_config.holding_dir}")
            shutil.rmtree(ui.move_config.holding_dir)
            ui.show_success("Deleted holding directory")
            logger.info("Successfully deleted holding directory")
        except OSError as e:
            logger.error(f"Failed to delete holding directory: {e}")
            ui.show_error(f"Failed to delete holding directory: {e}")
    
    return 0

def prepare_moves(
    files: List[Path],
    holding_dir: Path,
    preserve_structure: bool,
    group_id: int
) -> List[MoveOperation]:
    """Prepare move operations for selected files."""
    logger.info(f"Preparing moves for {len(files)} files to {holding_dir} (preserve_structure={preserve_structure})")
    moves = []
    used_destinations = set()
    
    # Find common parent for all files if preserving structure
    if preserve_structure and files:
        if len(files) == 1:
            common_parent = holding_dir.parent
            logger.debug(f"Single file case - using common parent: {common_parent}")
        else:
            common_parent = files[0].parent
            for file in files[1:]:
                while not str(file).startswith(str(common_parent)):
                    common_parent = common_parent.parent
            logger.debug(f"Multiple files case - using common parent: {common_parent}")
    
    for source in files:
        if preserve_structure:
            rel_path = source.relative_to(common_parent)
            dest = holding_dir / rel_path
            logger.debug(f"Preserving structure: {source} -> {dest}")
        else:
            dest = holding_dir / source.name
            logger.debug(f"Flat structure: {source} -> {dest}")
            
        # Handle name conflicts with existing files and planned moves
        base = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists() or dest in used_destinations:
            dest = dest.with_name(f"{base}_{counter}{suffix}")
            logger.debug(f"Handling conflict: using {dest}")
            counter += 1
            
        used_destinations.add(dest)
        moves.append(MoveOperation(source, dest, group_id))
    
    logger.info(f"Prepared {len(moves)} move operations")
    return moves

def execute_moves(moves: List[MoveOperation]) -> None:
    """Execute prepared move operations."""
    logger.info(f"Executing {len(moves)} move operations")
    for move in moves:
        try:
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Moving {move.source} -> {move.destination}")
            shutil.move(str(move.source), str(move.destination))
            move.executed = True
            logger.info(f"Successfully moved {move.source} to {move.destination}")
        except (OSError, IOError) as e:
            logger.error(f"Failed to move {move.source}: {e}")
            raise

if __name__ == "__main__":
    sys.exit(main()) 