"""Interactive UI components for ndetect."""

from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ndetect.exceptions import DiskSpaceError, FileOperationError, PermissionError
from ndetect.logging import setup_logging
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import MoveOperation, prepare_moves, select_keeper
from ndetect.types import Action
from ndetect.utils import format_preview_text


class InteractiveUI:
    """Interactive UI components using rich."""

    def __init__(
        self,
        console: Console,
        move_config: MoveConfig,
        preview_config: Optional[PreviewConfig] = None,
        retention_config: Optional[RetentionConfig] = None,
    ) -> None:
        self.console = console
        self.move_config = move_config
        self.preview_config = preview_config or PreviewConfig()
        self.retention_config = retention_config
        self.pending_moves: List[MoveOperation] = []
        self.logger = setup_logging(None)  # Add logger instance

    def show_scan_progress(self, paths: List[str]) -> None:
        """Show progress while scanning files."""
        self.logger.info_with_fields(
            "Starting file scan", operation="scan", paths=paths
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            progress.add_task("Scanning files...", total=None)

    def display_group(
        self, group_id: int, files: List[Path], similarity: float
    ) -> None:
        """Display a group of similar files."""
        self.logger.info_with_fields(
            "Displaying file group",
            operation="display",
            group_id=group_id,
            similarity=similarity,
            file_count=len(files),
            files=[str(f) for f in files],
        )

        # Show similarity based on group size
        if len(files) == 2:
            self.console.print(f"~{similarity:.2%} similar")
        else:
            self.console.print(f"~{similarity:.2%} avg. similarity")

        # Create a table for the files
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim")
        table.add_column("File", style="cyan")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", justify="right", style="yellow")

        # Add rows for each file
        for idx, file in enumerate(files, 1):
            stats = file.stat()
            table.add_row(
                str(idx),
                str(file),
                f"{stats.st_size:,} bytes",
                datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M"),
            )

        self.console.print(table)

    def prompt_for_action(self) -> Action:
        """Prompt for user action."""
        choice = Prompt.ask(
            "\nChoose action", choices=["k", "d", "m", "p", "s", "q"], default="k"
        )
        return {
            "k": Action.KEEP,
            "d": Action.DELETE,
            "m": Action.MOVE,
            "p": Action.PREVIEW,
            "s": Action.SIMILARITIES,
            "q": Action.QUIT,
        }[choice]

    def select_files(
        self, files: List[Path], prompt: str = "Select files"
    ) -> List[Path]:
        """Prompt user to select files from a list."""
        with suppress(KeyboardInterrupt):
            if self.retention_config:
                keeper = select_keeper(files, self.retention_config)
                self.console.print(f"\n[green]Selected keeper: {keeper}[/green]")
                return [f for f in files if f != keeper]

            indices = (
                Prompt.ask(f"\n{prompt} (space-separated numbers, 'all' or 'none')")
                .strip()
                .lower()
            )

            if not indices or indices == "none":
                return []
            if indices == "all":
                return files.copy()

            try:
                selected = []
                for idx in indices.split():
                    i = int(idx) - 1
                    if 0 <= i < len(files):
                        selected.append(files[i])
                return selected
            except ValueError:
                self.show_error(
                    "Invalid input. Please enter numbers, 'all', or 'none'."
                )
                return []

        return []

    def confirm(self, message: str) -> bool:
        """Prompt for confirmation."""
        self.logger.info_with_fields(
            "User confirmation requested", operation="confirm", prompt_message=message
        )
        return Confirm.ask(message)

    def add_pending_move(self, move: MoveOperation) -> None:
        """Add a move operation to the pending list."""
        self.logger.info_with_fields(
            "Adding pending move",
            operation="pending_move",
            source=str(move.source),
            destination=str(move.destination),
            group_id=move.group_id,
        )
        self.pending_moves.append(move)

    def show_success(self, message: str) -> None:
        """Show a success message."""
        self.logger.info_with_fields(message, operation="ui", type="success")
        self.console.print(f"[green]{message}[/green]")

    def show_error(self, message: str, details: Optional[str] = None) -> None:
        """Display error message with optional details."""
        error_text = Text()
        error_text.append("Error: ", style="bold red")
        error_text.append(message)

        if details:
            error_text.append("\n\nDetails: ", style="bold")
            error_text.append(details, style="italic")

        self.console.print(Panel(error_text, border_style="red"))

    def handle_file_operation_error(
        self, error: FileOperationError, operation: str
    ) -> None:
        """Handle file operation related errors with specific guidance."""
        if isinstance(error, DiskSpaceError):
            title = "Insufficient disk space"
            guidance = (
                f"Required: {error.required_bytes // 1024 / 1024:.1f} MB, "
                f"Available: {error.available_bytes // 1024 / 1024:.1f} MB"
            )
        elif isinstance(error, PermissionError):
            title = "Permission denied"
            guidance = (
                "Please ensure you have the necessary permissions to access the file."
            )
        else:
            title = f"Error during {operation}"
            guidance = f"{error.operation} failed for {error.path}: {str(error)}"

        self.show_error(title, guidance)
        self.logger.error_with_fields(
            f"Operation failed: {operation}",
            error_type=type(error).__name__,
            details=str(error),
            operation=operation,
            path=error.path,
        )

    def show_help(self) -> None:
        """Show help information."""
        self.logger.info_with_fields("Displaying help", operation="ui", type="help")
        self.console.print(
            Panel(
                "[cyan]k[/cyan]: Keep all files in this group\n"
                "[cyan]d[/cyan]: Delete selected files\n"
                "[cyan]m[/cyan]: Move selected files to holding directory",
                title="Available Actions",
                border_style="blue",
            )
        )

    def show_preview(self, files: List[Path]) -> None:
        """Show preview of file contents."""
        if not files:
            self.console.print("No files to preview")
            return

        for file in files:
            try:
                if not file.exists():
                    raise FileOperationError("File not found", str(file), "preview")

                if not file.is_file():
                    raise FileOperationError("Not a regular file", str(file), "preview")

                try:
                    content = file.read_text(errors="replace")
                except Exception as e:
                    raise FileOperationError(
                        f"Failed to read file: {e}", str(file), "preview"
                    ) from e

                preview = format_preview_text(
                    text=content,
                    max_lines=self.preview_config.max_lines,
                    max_chars=self.preview_config.max_chars,
                    truncation_marker=self.preview_config.truncation_marker,
                )

                self.console.print(
                    Panel(
                        preview,
                        title=f"[cyan]{file}[/cyan]",
                        subtitle=f"Size: {file.stat().st_size:,} bytes",
                        border_style="blue",
                    )
                )

            except FileOperationError as e:
                self.handle_file_operation_error(e, "preview")
            except UnicodeDecodeError:
                self.show_error(
                    f"Cannot preview {file}",
                    "File appears to be binary or uses an unsupported encoding",
                )
            except Exception as e:
                self.logger.error_with_fields(
                    "Unexpected error during preview",
                    operation="preview",
                    file=str(file),
                    error=str(e),
                )
                self.show_error("Preview failed", f"An unexpected error occurred: {e}")

    def create_moves(self, files: List[Path], *, group_id: int) -> List[MoveOperation]:
        """Create move operations for selected files."""
        self.logger.info_with_fields(
            "Creating move operations",
            operation="create_moves",
            group_id=group_id,
            files=[str(f) for f in files],
        )
        moves = prepare_moves(
            files=files,
            holding_dir=self.move_config.holding_dir / f"group_{group_id}",
            preserve_structure=self.move_config.preserve_structure,
            group_id=group_id,
        )
        return moves

    def display_move_preview(self, moves: List[MoveOperation]) -> None:
        """Display preview of move operations."""
        self.logger.info_with_fields(
            "Displaying move preview", operation="move_preview", total_moves=len(moves)
        )
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Source", style="cyan")
        table.add_column("Destination", style="green")

        for move in moves:
            table.add_row(str(move.source), str(move.destination))

        self.console.print(Panel(table, title="Move Preview", border_style="blue"))

    def format_similarity_table(
        self, group_files: List[Path], similarities: Dict[Tuple[Path, Path], float]
    ) -> Table:
        """Create a table for similarities display."""
        table = Table(show_header=True, header_style="bold magenta", width=200)
        table.add_column("File 1", style="cyan", width=80)
        table.add_column("File 2", style="cyan", width=80)
        table.add_column("Similarity", justify="right", style="green", width=12)

        for (file1, file2), sim in similarities.items():
            table.add_row(str(file1), str(file2), f"{sim:.2%}")

        return table

    def show_similarities(
        self, group_files: List[Path], similarities: Dict[Tuple[Path, Path], float]
    ) -> None:
        """Show pairwise similarities between files in a group."""
        table = self.format_similarity_table(group_files, similarities)
        self.console.print(
            Panel(table, title="Pairwise Similarities", border_style="blue")
        )
