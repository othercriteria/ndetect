"""File operations for ndetect."""

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from ndetect.models import RetentionConfig

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
    preserve_structure: bool,
    group_id: int,
    base_dir: Optional[Path] = None,
    retention_config: Optional[RetentionConfig] = None,
) -> List[MoveOperation]:
    """Prepare move operations for a group of files."""
    if retention_config:
        # Keep one file based on retention criteria
        keeper = select_keeper(files, retention_config, base_dir)
        files_to_move = [f for f in files if f != keeper]
    else:
        files_to_move = files

    moves: List[MoveOperation] = []
    used_names: Set[Path] = set()

    # If preserving structure, determine base directory
    if preserve_structure and files and not base_dir:
        base_dir = Path(os.path.commonpath([str(f) for f in files]))

    for file in files_to_move:
        if preserve_structure and base_dir:
            try:
                rel_path = file.relative_to(base_dir)
                dest = holding_dir / rel_path
            except ValueError:
                dest = holding_dir / file.name
        else:
            dest = holding_dir / file.name

        # Handle name conflicts
        base_dest = dest
        counter = 1
        while dest in used_names:
            dest = base_dest.parent / f"{base_dest.stem}_{counter}{base_dest.suffix}"
            counter += 1

        used_names.add(dest)
        moves.append(MoveOperation(source=file, destination=dest, group_id=group_id))

    return moves


def execute_moves(moves: List[MoveOperation]) -> None:
    """Execute the move operations."""
    for move in moves:
        # Create parent directories if they don't exist
        move.destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(move.source), str(move.destination))
            logger.info("Moved %s to %s", move.source, move.destination)
        except OSError as e:
            logger.error(
                "Failed to move %s to %s: %s", move.source, move.destination, e
            )
            raise
