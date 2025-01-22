"""Interactive UI components for ndetect."""

from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

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
        """Prompt user for action on current group."""
        action_map = {
            "d": Action.DELETE,
            "m": Action.MOVE,
            "n": Action.NEXT,
            "p": Action.PREVIEW,
            "s": Action.SIMILARITIES,
            "q": Action.QUIT,
            "h": Action.HELP,
            "": Action.NEXT,
        }

        choice = Prompt.ask(
            "\nWhat would you like to do with this group?",
            choices=[k for k in action_map if k != ""],
            default="n",
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
        # Get console width and calculate column widths
        console_width = self.console.width or 80  # Default to 80 if width not available

        # Reserve space for borders and padding (approximately 10 characters)
        available_width = console_width - 10

        # Allocate 40% of space each to file columns and 20% to similarity
        file_col_width = int(available_width * 0.4)
        sim_col_width = int(available_width * 0.2)

        table = Table(
            show_header=True, header_style="bold magenta", width=console_width
        )
        table.add_column("File 1", style="cyan", width=file_col_width)
        table.add_column("File 2", style="cyan", width=file_col_width)
        table.add_column(
            "Similarity", justify="right", style="green", width=sim_col_width
        )

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

    def _handle_keeper_selection(self, group: SimilarGroup) -> Optional[Path]:
        """Handle user input for keeper selection and return selected keeper."""
        self.display_files(group.files)  # Show numbered list of files
        keeper_input = Prompt.ask(
            "\nSelect keeper file number",
            choices=[str(i) for i in range(1, len(group.files) + 1)],
        )

        try:
            keeper_idx = int(keeper_input) - 1
            if 0 <= keeper_idx < len(group.files):
                return group.files[keeper_idx]
        except ValueError:
            self.show_error("Invalid keeper selection, using default")
        return None

    def _select_keeper(self, group: SimilarGroup) -> Path:
        """Select a keeper file from the group."""
        keeper = group.keeper or select_keeper(group.files, self.retention_config)
        self.console.print(f"\nDefault keeper selected: \n{keeper}")

        if Confirm.ask("Do you want to select a different keeper?"):
            new_keeper = self._handle_keeper_selection(group)
            if new_keeper:
                keeper = new_keeper

        return keeper

    def _display_keeper_selection_table(self, files: List[Path]) -> None:
        """Display a numbered table of files for keeper selection."""
        table = Table(show_header=True)
        table.add_column("#")
        table.add_column("File")
        for idx, file in enumerate(files, 1):
            table.add_row(str(idx), str(file))
        self.console.print(table)

    def _get_files_to_process(self, group: SimilarGroup) -> List[Path]:
        """Get list of files to process, excluding the keeper."""
        files = [f for f in group.files if f != group.keeper]
        if not files:
            self.console.print("[yellow]No files selected for operation[/yellow]")
        return files

    def _handle_dry_run(self, operation: str, files: List[Path]) -> None:
        """Handle dry run mode for file operations."""
        self.console.print(f"[yellow]Dry run: Would {operation} these files:[/yellow]")
        for file in files:
            self.console.print(f"  {file}")

    def _handle_file_operation(
        self,
        group: SimilarGroup,
        operation: str,
        operation_func: Callable[[List[Path]], None],
        confirm_message: Callable[[List[Path]], str],
    ) -> bool:
        """Handle a file operation with keeper selection and confirmation."""
        if not group.files:
            return False

        # Select keeper first
        self._select_keeper(group)
        if not group.keeper:
            return False

        if operation == "move":
            files_to_process = group.files
        elif operation == "delete":
            # Exclude the keeper from the delete operation
            files_to_process = self._get_files_to_process(group)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        if not files_to_process:
            return False

        if self.move_config and self.move_config.dry_run:
            if operation == "move":
                moves = prepare_moves(
                    files=files_to_process,
                    holding_dir=self.move_config.holding_dir,
                    preserve_structure=self.move_config.preserve_structure,
                    group_id=group.id,
                    base_dir=self.move_config.holding_dir.parent
                    if self.move_config
                    else None,
                    retention_config=self.retention_config,
                    keeper=group.keeper,
                )
                self._handle_dry_run_move(moves)
            elif operation == "delete":
                self._handle_dry_run_delete(files_to_process)
            return True

        if Confirm.ask(confirm_message(files_to_process)):
            operation_func(files_to_process)
            return True

        return False

    def _handle_dry_run_move(self, moves: List[MoveOperation]) -> None:
        """Handle dry-run display for move operations."""
        self.console.print("[cyan]Dry Run: The following files would be moved:[/cyan]")
        for move in moves:
            self.console.print(f"  {move.source} -> {move.destination}")

    def _handle_dry_run_delete(self, files: List[Path]) -> None:
        """Handle dry-run display for delete operations."""
        self.console.print(
            "[cyan]Dry Run: The following files would be deleted:[/cyan]"
        )
        for file in files:
            self.console.print(f"  {file}")

    def handle_delete(self, files: List[Path]) -> bool:
        """Handle deletion of files."""
        if not files:
            return False

        group = SimilarGroup(files=files, similarity=1.0, id=1)
        group.keeper = select_keeper(files, self.retention_config)
        self.console.print(f"\nDefault keeper selected: \n{group.keeper}")

        if Confirm.ask("Do you want to select a different keeper?"):
            new_keeper = self._handle_keeper_selection(group)
            if new_keeper:
                group.keeper = new_keeper

        files_to_delete = [f for f in files if f != group.keeper]
        if not files_to_delete:
            self.console.print("[yellow]No files selected for deletion[/yellow]")
            return False

        if self.move_config.dry_run:
            self._handle_dry_run("delete", files_to_delete)
            return False

        if Confirm.ask("Are you sure you want to delete these files?"):
            delete_files(files_to_delete)
            return True

        return False

    def handle_move(self, files: List[Path]) -> bool:
        """Handle moving of files."""
        if not files:
            return False

        group = SimilarGroup(files=files, similarity=1.0, id=1)
        group.keeper = select_keeper(files, self.retention_config)
        self.console.print(f"\nDefault keeper selected: \n{group.keeper}")

        if Confirm.ask("Do you want to select a different keeper?"):
            new_keeper = self._handle_keeper_selection(group)
            if new_keeper:
                group.keeper = new_keeper

        moves = prepare_moves(
            files=files,
            holding_dir=self.move_config.holding_dir,
            preserve_structure=self.move_config.preserve_structure,
            retention_config=self.retention_config,
            keeper=group.keeper,
        )

        if not moves:
            self.console.print("[yellow]No files selected for moving[/yellow]")
            return False

        if self.move_config.dry_run:
            self._handle_dry_run("move", [m.source for m in moves])
            return False

        if Confirm.ask("Are you sure you want to move these files?"):
            execute_moves(moves)
            return True

        return False

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
