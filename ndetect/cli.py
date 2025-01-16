"""Command-line interface for ndetect."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from ndetect.exceptions import handle_error
from ndetect.logging import StructuredLogger, setup_logging
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig, TextFile
from ndetect.operations import MoveOperation, execute_moves, prepare_moves
from ndetect.similarity import SimilarityGraph
from ndetect.text_detection import scan_paths
from ndetect.types import SimilarGroup
from ndetect.ui import InteractiveUI

__all__ = [
    "parse_args",
    "scan_paths",
    "prepare_moves",
    "execute_moves",
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
        "-v",
        "--verbose",
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
        help="Directory to move duplicate files to (default: ./holding)",
    )
    parser.add_argument(
        "--flat-holding",
        action="store_true",
        help="Don't preserve directory structure when moving files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--retention",
        choices=["newest", "oldest", "shortest_path", "largest", "smallest"],
        default="newest",
        help="Strategy for selecting which file to keep (default: newest)",
    )
    parser.add_argument(
        "--priority-paths",
        nargs="+",
        help="Priority paths/patterns for retention (e.g., 'important/*')",
    )
    parser.add_argument(
        "--priority-first",
        action="store_true",
        help="Apply priority paths before other retention criteria",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    args = parse_args(argv if argv is not None else None)
    setup_logging(args.log_file, args.verbose)
    console = Console()

    try:
        # Create configurations
        retention_config = RetentionConfig(
            strategy=args.retention,
            priority_paths=args.priority_paths or [],
            priority_first=args.priority_first,
        )

        move_config = MoveConfig(
            holding_dir=args.holding_dir or Path("duplicates"),
            preserve_structure=True,
            dry_run=args.dry_run,
        )

        preview_config = PreviewConfig(
            max_chars=args.preview_chars,
            max_lines=args.preview_lines,
        )

        # Get the base directory from the first provided path
        base_dir = Path(args.paths[0]).parent if len(args.paths) == 1 else Path.cwd()

        ui = InteractiveUI(
            console=console,
            move_config=move_config,
            preview_config=preview_config,
            retention_config=retention_config,
        )

        text_files = scan_paths(
            args.paths,
            min_printable_ratio=args.min_printable_ratio,
            num_perm=args.num_perm,
            shingle_size=args.shingle_size,
        )
        if not text_files:
            console.print("[red]No valid text files found.[/red]")
            return 1

        console.print(f"Found {len(text_files)} text files.")

        if args.mode == "interactive":
            return handle_interactive_mode(ui, text_files, args.threshold)
        elif args.mode == "non-interactive":
            return handle_non_interactive_mode(
                console=console,
                text_files=text_files,
                threshold=args.threshold,
                base_dir=base_dir,
                holding_dir=args.holding_dir,
                dry_run=args.dry_run,
                log_file=args.log_file,
                retention_config=retention_config,
            )

        console.print("[red]Unknown mode specified.[/red]")
        return 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 130
    except Exception as e:
        return handle_error(console, e)


def build_similarity_graph(
    text_files: List[TextFile], threshold: float, progress: Progress
) -> SimilarityGraph:
    """Build similarity graph with progress display."""
    task = progress.add_task("Building similarity graph...", total=len(text_files))
    graph = SimilarityGraph(threshold=threshold)

    batch_size = 1000
    for i in range(0, len(text_files), batch_size):
        batch = text_files[i : (i + batch_size)]
        graph.add_files(batch)
        progress.advance(task, len(batch))

    return graph


def process_group(
    ui: InteractiveUI, graph: SimilarityGraph, group: SimilarGroup
) -> str:
    """Process a group of similar files."""
    ui.display_group(group.id, group.files, group.similarity)

    while True:
        action = ui.prompt_for_action()

        if action == "i":
            ui.show_preview(group.files)
        elif action == "m":
            selected = ui.select_files(group.files, "Select files to move")
            if selected:
                moves = ui.create_moves(selected, group_id=group.id)
                ui.pending_moves.extend(moves)
                return "k"
        elif action == "d":
            ui.show_error("Delete operation not implemented yet")
        elif action in ["k", "q"]:
            return action

    return "k"


def handle_interactive_mode(
    ui: InteractiveUI, text_files: List[TextFile], threshold: float
) -> int:
    """Handle interactive mode with rich UI."""
    logger = setup_logging(None)  # Add logger for interactive mode

    logger.info_with_fields(
        "Starting interactive mode",
        operation="start",
        total_files=len(text_files),
        threshold=threshold,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=ui.console,
    ) as progress:
        graph = build_similarity_graph(text_files, threshold, progress)
        logger.info_with_fields(
            "Graph built", operation="analysis", similar_groups=len(graph.get_groups())
        )

    while True:
        groups = graph.get_groups()
        if not groups:
            if ui.pending_moves:
                logger.info_with_fields(
                    "Processing pending moves",
                    operation="cleanup",
                    total_moves=len(ui.pending_moves),
                )
                return handle_cleanup_phase(ui)
            logger.info_with_fields(
                "No more duplicate groups found", operation="complete", status="success"
            )
            ui.show_success("No more duplicate groups found.")
            return 0

        logger.info_with_fields(
            "Processing group", operation="group", group_size=len(groups[0].files)
        )
        action = process_group(ui, graph, groups[0])
        if action == "q":
            logger.info_with_fields("User quit", operation="complete", status="quit")
            return 0
        elif action == "k":
            logger.info_with_fields(
                "Group kept",
                operation="group",
                status="kept",
                files=[str(f) for f in groups[0].files],
            )
            graph.remove_group(groups[0].files)


def setup_non_interactive_logging(log_file: Optional[Path]) -> StructuredLogger:
    """Configure logging for non-interactive mode."""
    return setup_logging(log_file=log_file)


def process_similar_groups(
    console: Console,
    graph: SimilarityGraph,
    base_dir: Optional[Path],
    holding_dir: Path,
    retention_config: Optional[RetentionConfig],
    dry_run: bool,
    logger: StructuredLogger,
) -> List[MoveOperation]:
    """Process groups of similar files and prepare moves."""
    groups = graph.get_groups()
    if not groups:
        console.print("[yellow]No similar files found[/yellow]")
        logger.info_with_fields("No similar files found", operation="process_groups")
        return []

    all_moves: List[MoveOperation] = []
    for i, group in enumerate(groups, 1):
        moves = prepare_moves(
            files=group.files,
            holding_dir=holding_dir / f"group_{i}",
            preserve_structure=True,
            group_id=i,
            base_dir=base_dir,
            retention_config=retention_config,
        )

        for move in moves:
            rel_src = move.source.relative_to(base_dir) if base_dir else move.source
            rel_dst = move.destination

            logger.info_with_fields(
                "Processing move operation",
                operation="move",
                dry_run=dry_run,
                source=str(rel_src),
                destination=str(rel_dst),
                group_id=i,
            )

            msg = f"  {rel_src} -> {rel_dst}"
            if dry_run:
                console.print(f"[dim]{msg}[/dim]")
            else:
                console.print(msg)

        all_moves.extend(moves)

    logger.info_with_fields(
        "Finished processing groups",
        operation="process_groups",
        total_groups=len(groups),
        total_moves=len(all_moves),
    )
    return all_moves


def handle_non_interactive_mode(
    console: Console,
    text_files: List["TextFile"],
    threshold: float,
    base_dir: Optional[Path] = None,
    holding_dir: Optional[Path] = None,
    dry_run: bool = False,
    log_file: Optional[Path] = None,
    retention_config: Optional[RetentionConfig] = None,
) -> int:
    """Handle non-interactive mode with automated processing."""
    logger = setup_non_interactive_logging(log_file)
    holding_dir = holding_dir or Path("duplicates")

    try:
        logger.info_with_fields(
            "Starting non-interactive processing",
            operation="start",
            total_files=len(text_files),
            threshold=threshold,
            base_dir=str(base_dir) if base_dir else None,
            holding_dir=str(holding_dir),
            dry_run=dry_run,
        )

        with console.status("[bold green]Analyzing file similarities..."):
            graph = SimilarityGraph(threshold=threshold)
            graph.add_files(text_files)

        logger.info_with_fields(
            "File analysis complete",
            operation="analysis",
            similar_groups=len(graph.get_groups()),
        )

        all_moves = process_similar_groups(
            console=console,
            graph=graph,
            base_dir=base_dir,
            holding_dir=holding_dir,
            retention_config=retention_config,
            dry_run=dry_run,
            logger=logger,
        )

        if not all_moves:
            logger.info_with_fields(
                "No moves to execute", operation="complete", status="no_moves"
            )
            return 0

        if dry_run:
            logger.info_with_fields(
                "Dry run complete",
                operation="complete",
                status="dry_run",
                planned_moves=len(all_moves),
            )
            console.print(f"\nWould move {len(all_moves)} files")
            return 0

        try:
            logger.info_with_fields(
                "Executing moves", operation="move_start", total_moves=len(all_moves)
            )
            execute_moves(all_moves)
            logger.info_with_fields(
                "Moves completed successfully",
                operation="complete",
                status="success",
                total_moves=len(all_moves),
            )
            console.print(f"\n[green]Successfully moved {len(all_moves)} files[/green]")
            return 0
        except Exception as e:
            logger.error_with_fields(
                "Move operation failed",
                operation="complete",
                status="error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return handle_error(console, e)

    finally:
        if log_file:
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


def handle_cleanup_phase(ui: InteractiveUI) -> int:
    """Handle the cleanup phase after processing groups."""
    if not ui.confirm("Execute pending moves?"):
        return 0

    try:
        execute_moves(ui.pending_moves)
        ui.show_success(f"Successfully moved {len(ui.pending_moves)} files")
        return 0
    except Exception as e:
        return handle_error(ui.console, e)


if __name__ == "__main__":
    sys.exit(main())
