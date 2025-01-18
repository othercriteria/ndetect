"""Interactive UI components for ndetect."""

from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ndetect.exceptions import DiskSpaceError, FileOperationError, PermissionError
from ndetect.logging import StructuredLogger, get_logger
from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import (
    MoveOperation,
    delete_files,
    execute_moves,
    prepare_moves,
    select_keeper,
)
from ndetect.types import Action, SimilarGroup
from ndetect.utils import format_preview_text

logger = get_logger()


class InteractiveUI:
    """Interactive UI components using rich."""

    def __init__(
        self,
        console: Console,
        move_config: MoveConfig,
        retention_config: RetentionConfig,
        preview_config: Optional[PreviewConfig] = None,
        logger: Optional[StructuredLogger] = None,
    ) -> None:
        """Initialize the UI."""
        self.console = console
        self.move_config = move_config
        self.retention_config = retention_config
        self.preview_config = preview_config or PreviewConfig()
        self.logger = logger or get_logger()
        self.pending_moves: List[MoveOperation] = []

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

    def display_group(self, group: SimilarGroup) -> None:
        """Display a group of similar files."""
        self.logger.info_with_fields(
            "Displaying file group",
            operation="display",
            group_id=group.id,
            similarity=group.similarity,
            file_count=len(group.files),
            files=[str(f) for f in group.files],
        )

        # Show similarity based on group size
        if len(group.files) == 2:
            self.console.print(f"~{group.similarity:.2%} similar")
        else:
            self.console.print(f"~{group.similarity:.2%} avg. similarity")

        # Create a table for the files
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim")
        table.add_column("File", style="cyan")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", justify="right", style="yellow")

        # Add rows for each file
        for idx, file in enumerate(group.files, 1):
            stats = file.stat()
            table.add_row(
                str(idx),
                str(file),
                f"{stats.st_size:,} bytes",
                datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M"),
            )

        self.console.print(table)

        # Select keeper if not already set
        if not group.keeper:
            group.keeper = select_keeper(group.files, self.retention_config)
            self.console.print(
                f"\n[green]Default keeper selected: {group.keeper}[/green]"
            )

    def prompt_for_action(self) -> Action:
        """Prompt for user action."""
        action_map: Dict[str, Action] = {
            "k": Action.KEEP,
            "d": Action.DELETE,
            "m": Action.MOVE,
            "p": Action.PREVIEW,
            "s": Action.SIMILARITIES,
            "h": Action.HELP,
            "q": Action.QUIT,
        }

        choice = Prompt.ask(
            "\nChoose action", choices=list(action_map.keys()), default="k"
        )
        return action_map[choice]

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
        self.pending_moves.append(move)

    def clear_pending_moves(self) -> None:
        """Clear all pending move operations."""
        self.pending_moves.clear()

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
                "[cyan]m[/cyan]: Move selected files to holding directory\n"
                "[cyan]p[/cyan]: Preview file contents\n"
                "[cyan]s[/cyan]: Show similarities between files\n"
                "[cyan]q[/cyan]: Quit program",
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

    def show_delete_preview(self, files: List[Path]) -> None:
        """Show preview of files to be deleted."""
        panel = Panel(
            "\n".join(str(f) for f in files),
            title="Files to Delete",
            subtitle="Delete Preview",
        )
        self.console.print(panel)

    def _handle_file_operation(
        self,
        group: SimilarGroup,
        operation: str,
        operation_func: Callable[[List[Path]], None],
        confirm_message: Union[str, Callable[[List[Path]], str]],
    ) -> bool:
        """Handle file operations with retention-based selection."""
        if not group.files:
            return False

        files_to_process = [f for f in group.files if f != group.keeper]
        self.console.print(f"\n[green]Selected keeper: {group.keeper}[/green]")

        # Allow user to override the selection
        try:
            selected_indices = self._prompt_for_indices(
                group.files,
                f"Enter file numbers to {operation} (comma-separated, or Enter "
                "to accept default)",
                keeper=group.keeper,
            )
            if selected_indices:  # Only override if user provided input
                files_to_process = [group.files[i - 1] for i in selected_indices]
                if group.keeper in files_to_process:
                    files_to_process.remove(group.keeper)
        except ValueError as e:
            self.console.print(f"[red]Invalid selection: {e}[/red]")
            return False

        if not files_to_process:
            self.console.print(f"[yellow]No files selected for {operation}[/yellow]")
            return False

        # Get confirmation message
        if callable(confirm_message):
            msg = confirm_message(files_to_process)
        else:
            msg = confirm_message

        # Confirm operation
        if not Confirm.ask(msg):
            return False

        try:
            operation_func(files_to_process)
            self.console.print(
                f"Successfully {operation}d {len(files_to_process)} files"
            )
            return True
        except Exception as e:
            self.console.print(f"[red]Error during {operation}: {e}[/red]")
            return False

    def handle_delete(self, files: List[Path]) -> bool:
        """Handle deletion of selected files."""
        group = SimilarGroup(id=1, files=files, similarity=1.0)
        # Select keeper before operation
        group.keeper = select_keeper(files, self.retention_config)
        return self._handle_file_operation(
            group=group,
            operation="delete",
            operation_func=delete_files,
            confirm_message="Are you sure you want to delete these files?",
        )

    def handle_move(self, files: List[Path]) -> bool:
        """Handle moving selected files to holding directory."""
        if not self.move_config:
            self.console.print("[red]Move operation not configured[/red]")
            return False

        group = SimilarGroup(id=1, files=files, similarity=1.0)
        # Select keeper before operation
        group.keeper = select_keeper(files, self.retention_config)
        return self._handle_file_operation(
            group=group,
            operation="move",
            operation_func=lambda files: execute_moves(
                prepare_moves(
                    files,
                    self.move_config.holding_dir,
                    self.move_config.preserve_structure,
                )
            ),
            confirm_message=lambda files: (
                f"Move {len(files)} files to {self.move_config.holding_dir}?"
            ),
        )

    def _prompt_for_indices(
        self, files: List[Path], prompt: str, keeper: Optional[Path] = None
    ) -> List[int]:
        """Prompt for file indices and validate input."""
        if not files:
            return []

        # Get user input
        response = Prompt.ask(prompt).strip()

        # Handle empty input
        if not response:
            if keeper is not None:
                # With keeper, empty input means select all except keeper
                return [i for i, f in enumerate(files, 1) if f != keeper]
            # Without keeper, empty input means no selection
            return []

        # Parse and validate indices
        try:
            indices = [int(i.strip()) for i in response.split(",")]
            valid_indices = []
            for idx in indices:
                if idx < 1 or idx > len(files):
                    raise ValueError(f"Invalid index: {idx}")
                valid_indices.append(idx)
            return valid_indices
        except ValueError as e:
            raise ValueError(f"Invalid input: {e}") from e

    def display_files(self, files: List[Path]) -> None:
        """Display a numbered list of files with their details."""
        if not files:
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", justify="right")
        table.add_column("File", no_wrap=True)
        table.add_column("Size", justify="right")
        table.add_column("Modified", justify="right")

        for i, file in enumerate(files, 1):
            try:
                stat = file.stat()
                size = f"{stat.st_size:,} bytes"
                modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                table.add_row(str(i), str(file), size, modified)
            except OSError as e:
                self.logger.error_with_fields(
                    f"Failed to get file stats: {e}",
                    operation="display",
                    file=str(file),
                    error=str(e),
                )
                table.add_row(str(i), str(file), "ERROR", "ERROR")

        self.console.print(table)
