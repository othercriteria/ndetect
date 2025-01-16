"""File operations for ndetect."""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ndetect.models import RetentionConfig

from .exceptions import FileOperationError, PermissionError
from .utils import check_disk_space, get_total_size

logger = logging.getLogger(__name__)


@dataclass
class MoveOperation:
    """Record of a move operation."""

    source: Path
    destination: Path
    group_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False


# ruff: noqa: C901
def select_keeper(
    files: List[Path], config: RetentionConfig, base_dir: Optional[Path] = None
) -> Path:
    """Select which file to keep based on retention criteria."""
    if not files:
        raise ValueError("No files provided")

    # Handle priority paths first if configured
    if config.priority_paths and config.priority_first:
        for pattern in config.priority_paths:
            for file in files:
                if file.match(pattern):
                    return file

    # Apply the selected strategy
    match config.strategy:
        case "newest":
            return max(files, key=lambda p: p.stat().st_mtime)
        case "oldest":
            return min(files, key=lambda p: p.stat().st_mtime)
        case "largest":
            return max(files, key=lambda p: p.stat().st_size)
        case "smallest":
            return min(files, key=lambda p: p.stat().st_size)
        case "shortest_path":
            if base_dir:
                return min(files, key=lambda p: len(str(p.relative_to(base_dir))))
            return min(files, key=lambda p: len(str(p)))
        case _:
            raise ValueError(f"Unknown retention strategy: {config.strategy}")


def prepare_moves(
    files: List[Path],
    holding_dir: Path,
    preserve_structure: bool = True,
    group_id: int = 0,
    base_dir: Optional[Path] = None,
    retention_config: Optional[RetentionConfig] = None,
) -> List[MoveOperation]:
    """Prepare move operations for a group of files."""
    if not files:
        return []

    # Select which file to keep based on retention config
    keeper = select_keeper(files, retention_config or RetentionConfig(), base_dir)

    # Create moves for all files except the keeper
    moves: List[MoveOperation] = []
    for file in files:
        if file == keeper:
            continue

        if preserve_structure and base_dir:
            # Preserve directory structure relative to base_dir
            try:
                rel_path = file.relative_to(base_dir)
                destination = holding_dir / rel_path
            except ValueError:
                # If file is not under base_dir, use just the filename
                destination = holding_dir / file.name
        else:
            destination = holding_dir / file.name

        moves.append(
            MoveOperation(
                source=file,
                destination=destination,
                group_id=group_id,
            )
        )

    return moves


def execute_moves(moves: List[MoveOperation]) -> None:
    """Execute move operations with enhanced error handling."""
    if not moves:
        return

    # Pre-flight checks
    source_files = [m.source for m in moves]
    total_size = get_total_size(source_files)

    # Group moves by destination directory
    by_dest: dict[Path, list[MoveOperation]] = {}
    for move in moves:
        dest_dir = move.destination.parent
        by_dest.setdefault(dest_dir, []).append(move)

    # Check disk space on first destination directory
    # (assumes all destinations are on same filesystem)
    if by_dest:
        first_dest = next(iter(by_dest))
        check_disk_space(first_dest, total_size)

    # Execute moves with rollback capability
    completed: List[MoveOperation] = []
    try:
        for move in moves:
            try:
                # Create parent directories if needed
                move.destination.parent.mkdir(parents=True, exist_ok=True)
                # Attempt the move
                shutil.move(str(move.source), str(move.destination))
                completed.append(move)
            except PermissionError as err:
                raise PermissionError(str(move.source), "move") from err
            except OSError as err:
                raise FileOperationError(str(err), str(move.source), "move") from err
    except Exception as e:
        # Attempt rollback of completed moves
        logger.error("Move operation failed, attempting rollback: %s", e)
        rollback_moves(completed)
        raise


def rollback_moves(completed_moves: List[MoveOperation]) -> None:
    """Attempt to rollback completed moves."""
    for move in reversed(completed_moves):
        try:
            shutil.move(str(move.destination), str(move.source))
            logger.info("Rolled back move: %s -> %s", move.destination, move.source)
        except OSError as e:
            logger.error(
                "Failed to rollback move %s -> %s: %s", move.destination, move.source, e
            )
