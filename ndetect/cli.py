"""Command-line interface for ndetect."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from ndetect import __version__
from ndetect.exceptions import (
    handle_error,
)
from ndetect.logging import StructuredLogger, setup_logging
from ndetect.models import (
    CLIConfig,
    RetentionConfig,
    TextFile,
)
from ndetect.operations import MoveOperation, execute_moves, prepare_moves
from ndetect.similarity import SimilarityGraph
from ndetect.text_detection import scan_paths
from ndetect.types import Action, SimilarGroup
from ndetect.ui import InteractiveUI

__all__ = [
    "parse_args",
    "scan_paths",
    "prepare_moves",
    "execute_moves",
]

logger = logging.getLogger(__name__)


def parse_args(argv: Optional[List[str]] = None) -> CLIConfig:
    """Parse command line arguments into unified config."""
    parser = argparse.ArgumentParser(
        description="Detect and manage similar text files."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ndetect {__version__}",
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
        help="Maximum number of worker processes for parallel scanning",
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
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        default=True,
        help="Follow symbolic links when scanning (default: True)",
    )
    parser.add_argument(
        "--no-follow-symlinks",
        action="store_false",
        dest="follow_symlinks",
        help="Do not follow symbolic links when scanning",
    )
    parser.add_argument(
        "--include-empty",
        action="store_false",
        dest="skip_empty",
        help="Include empty (zero-byte) files in analysis",
    )
    parser.add_argument(
        "--max-symlink-depth",
        type=int,
        default=10,
        help="Maximum depth when following symbolic links (default: 10)",
    )

    args = parser.parse_args(argv)

    # Convert args namespace to CLIConfig
    return CLIConfig(
        mode=args.mode,
        paths=args.paths,
        threshold=args.threshold,
        dry_run=args.dry_run,
        verbose=args.verbose,
        log_file=args.log_file,
        min_printable_ratio=args.min_printable_ratio,
        num_perm=args.num_perm,
        shingle_size=args.shingle_size,
        follow_symlinks=args.follow_symlinks,
        max_symlink_depth=args.max_symlink_depth,
        skip_empty=args.skip_empty,
        preview_chars=args.preview_chars,
        preview_lines=args.preview_lines,
        holding_dir=args.holding_dir,
        flat_holding=args.flat_holding,
        retention_strategy=args.retention,
        priority_paths=args.priority_paths,
        priority_first=args.priority_first,
        max_workers=args.max_workers,
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        config = parse_args(argv if argv is not None else None)
        logger = setup_logging(config.log_file, config.verbose)
        console = Console()

        # Scan files first (common to both modes)
        text_files = scan_paths(
            paths=config.paths,
            min_printable_ratio=config.min_printable_ratio,
            num_perm=config.num_perm,
            shingle_size=config.shingle_size,
            follow_symlinks=config.follow_symlinks,
            max_workers=config.max_workers,
        )

        if config.mode == "interactive":
            return handle_interactive_mode(
                config=config,
                console=console,
                text_files=text_files,
                logger=logger,
            )
        else:
            return handle_non_interactive_mode(
                config=config,
                console=console,
                text_files=text_files,
                logger=logger,
            )
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
) -> Action:
    """Process a group of similar files."""
    ui.display_group(group.id, group.files, group.similarity)

    while True:
        action = ui.prompt_for_action()
        match action:
            case Action.DELETE:
                files = ui.select_files(group.files, "Select files to delete")
                if files:
                    ui.handle_delete(files)
                    graph.remove_files(files)
                return action
            case Action.PREVIEW:
                ui.show_preview(group.files)
            case Action.SIMILARITIES:
                similarities = graph.get_group_similarities(group.files)
                ui.show_similarities(group.files, similarities)
            case Action.MOVE:
                selected = ui.select_files(group.files, "Select files to move")
                if selected:
                    moves = ui.create_moves(selected, group_id=group.id)
                    ui.pending_moves.extend(moves)
                    return Action.KEEP
            case Action.KEEP:
                return action
            case Action.QUIT:
                return action


def handle_interactive_mode(
    config: CLIConfig,
    console: Console,
    text_files: List[TextFile],
    logger: StructuredLogger,
) -> int:
    """Handle interactive mode with rich UI."""
    ui = InteractiveUI(
        console=console,
        move_config=config.move_config,
        preview_config=config.preview_config,
        retention_config=config.retention_config,
        logger=logger,
    )

    logger.info_with_fields(
        "Starting interactive mode",
        operation="start",
        total_files=len(text_files),
        threshold=config.threshold,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        graph = build_similarity_graph(text_files, config.threshold, progress)

    return process_interactive_groups(ui, graph)


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
    config: CLIConfig,
    console: Console,
    text_files: List[TextFile],
    logger: StructuredLogger,
) -> int:
    """Handle non-interactive mode operations."""
    if not text_files:
        logger.info_with_fields(
            "No valid text files found",
            operation="complete",
            status="no_files",
        )
        return 0

    graph = SimilarityGraph(threshold=config.threshold)
    graph.add_files(text_files)
    similar_groups = list(graph.get_groups())

    if not similar_groups:
        logger.info_with_fields(
            "No similar files found",
            operation="complete",
            status="no_groups",
        )
        return 0

    moves = process_similar_groups(
        console=console,
        graph=graph,
        base_dir=config.base_dir,
        holding_dir=config.holding_dir,
        retention_config=config.retention_config,
        dry_run=config.dry_run,
        logger=logger,
    )

    if not moves:
        return 0

    if not config.dry_run:
        execute_moves(moves)
        logger.info_with_fields(
            "Moves completed successfully",
            operation="complete",
            status="success",
        )

    return 0


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


def process_interactive_groups(ui: InteractiveUI, graph: SimilarityGraph) -> int:
    """Process groups in interactive mode."""
    for group in graph.get_groups():
        action = process_group(ui, graph, group)
        if action == Action.QUIT:
            break

    return handle_cleanup_phase(ui)


if __name__ == "__main__":
    sys.exit(main())
