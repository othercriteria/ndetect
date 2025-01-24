"""File operations for ndetect."""

import builtins
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ndetect.logging import get_logger
from ndetect.models import RetentionConfig

from .exceptions import FileOperationError, PermissionError
from .utils import check_disk_space, get_total_size

# Get a properly typed logger instance
logger = get_logger()


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

    logger.info_with_fields(
        "Selecting keeper file",
        operation="select_keeper",
        strategy=config.strategy,
        total_files=len(files),
        priority_first=config.priority_first if config.priority_paths else False,
    )

    # Handle priority paths first if configured
    if config.priority_paths and config.priority_first:
        for pattern in config.priority_paths:
            for file in files:
                if file.match(pattern):
                    logger.info_with_fields(
                        "Selected keeper by priority path",
                        operation="select_keeper",
                        status="priority",
                        pattern=pattern,
                        keeper=str(file),
                    )
                    return file

    # Apply the selected strategy
    keeper = None
    match config.strategy:
        case "newest":
            keeper = max(files, key=lambda p: p.stat().st_mtime)
        case "oldest":
            keeper = min(files, key=lambda p: p.stat().st_mtime)
        case "largest":
            keeper = max(files, key=lambda p: p.stat().st_size)
        case "smallest":
            keeper = min(files, key=lambda p: p.stat().st_size)
        case "shortest_path":
            if base_dir:
                keeper = min(files, key=lambda p: len(str(p.relative_to(base_dir))))
            else:
                keeper = min(files, key=lambda p: len(str(p)))
        case _:
            raise ValueError(f"Unknown retention strategy: {config.strategy}")

    logger.info_with_fields(
        "Selected keeper by strategy",
        operation="select_keeper",
        status="strategy",
        strategy=config.strategy,
        keeper=str(keeper),
    )
    return keeper


def prepare_moves(
    files: List[Path],
    holding_dir: Path,
    preserve_structure: bool = True,
    group_id: int = 0,
    base_dir: Optional[Path] = None,
    retention_config: Optional[RetentionConfig] = None,
    keeper: Optional[Path] = None,
) -> List[MoveOperation]:
    """Prepare move operations for a group of files."""
    if not files:
        return []

    # Use the provided keeper if available; otherwise, select based on config
    if keeper is None:
        if retention_config is None:
            retention_config = RetentionConfig()
        keeper = select_keeper(files, retention_config, base_dir)

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
    """Execute move operations with structured logging and error handling."""
    if not moves:
        return

    # Calculate total size needed across all destinations
    total_size = get_total_size([move.source for move in moves])
    executed_moves: List[MoveOperation] = []

    logger.info_with_fields(
        "Starting move operations",
        operation="move_batch",
        total_files=len(moves),
        total_size=total_size,
    )

    try:
        # Check disk space for all destinations first
        destination_dirs = {move.destination.parent for move in moves}
        for dest_dir in destination_dirs:
            check_disk_space(dest_dir, total_size)

        # Execute moves
        for move in moves:
            try:
                logger.debug_with_fields(
                    f"Moving file {move.source} to {move.destination}",
                    operation="move",
                    source=str(move.source),
                    destination=str(move.destination),
                    group_id=move.group_id,
                    file_size=move.source.stat().st_size,
                )

                move.destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(move.source), str(move.destination))
                move.executed = True
                executed_moves.append(move)

            except OSError as e:
                # Roll back executed moves
                rollback_moves(executed_moves)

                if isinstance(e, PermissionError):
                    raise PermissionError(str(move.source), "move") from e
                else:
                    raise FileOperationError(str(e), str(move.source), "move") from e

    except Exception as e:
        # Log the error and roll back any executed moves
        logger.error_with_fields(
            "File operation failed",
            operation="move",
            error=str(e),
            error_type=type(e).__name__,
            # Only include file details if we have a current move
            **(
                {
                    "source": str(moves[0].source),
                    "destination": str(moves[0].destination),
                }
                if moves
                else {}
            ),
        )
        rollback_moves(executed_moves)
        raise


def rollback_moves(moves: List[MoveOperation]) -> None:
    """Roll back executed moves in case of failure."""
    logger.warning_with_fields(
        "Rolling back moves due to error", operation="rollback", total_moves=len(moves)
    )

    for move in reversed(moves):
        if move.executed:
            try:
                shutil.move(str(move.destination), str(move.source))
                move.executed = False
                logger.debug_with_fields(
                    f"Rolled back move from {move.destination} to {move.source}",
                    operation="rollback",
                    source=str(move.source),
                    destination=str(move.destination),
                )
            except OSError as e:
                logger.error_with_fields(
                    "Failed to roll back move",
                    operation="rollback",
                    error=str(e),
                    source=str(move.source),
                    destination=str(move.destination),
                )


def delete_files(files: List[Path]) -> None:
    """Delete files with structured logging and error handling."""
    if not files:
        return

    logger.info_with_fields(
        "Starting delete operations",
        operation="delete_batch",
        total_files=len(files),
    )

    deleted_files: List[Path] = []

    try:
        for file in files:
            try:
                logger.debug_with_fields(
                    f"Deleting file {file}",
                    operation="delete",
                    file=str(file),
                    file_size=file.stat().st_size,
                )

                file.unlink()
                deleted_files.append(file)

            except OSError as e:
                logger.error_with_fields(
                    "File deletion failed",
                    operation="delete",
                    error=str(e),
                    error_type=type(e).__name__,
                    file=str(file),
                )

                # Use our custom PermissionError
                if isinstance(e, builtins.PermissionError):
                    raise PermissionError(str(file), "delete") from e
                # Wrap other OSErrors in FileOperationError
                raise FileOperationError(str(e), str(file), "delete") from e

    except Exception as e:
        # Only log non-OSError exceptions at the top level
        if not isinstance(e, (PermissionError, FileOperationError)):
            logger.error_with_fields(
                "File deletion failed",
                operation="delete",
                error=str(e),
                error_type=type(e).__name__,
                file=str(files[0]) if files else None,
            )
        raise
