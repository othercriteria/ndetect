"""Interactive UI components using rich."""

from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ndetect.models import MoveConfig, PreviewConfig, RetentionConfig
from ndetect.operations import MoveOperation, prepare_moves, select_keeper


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

    def show_scan_progress(self, paths: List[str]) -> None:
        """Show progress while scanning files."""
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

    def prompt_action(self) -> str:
        """Prompt user for action on current group."""
        self.console.print("\nAvailable actions:", style="bold")
        actions = {
            "k": "Keep all files",
            "d": "Delete duplicates",
            "m": "Move duplicates to holding directory",
            "i": "Show detailed information",
            "q": "Quit",
        }

        # Explicitly set style for all action descriptions and disable markup
        for key, desc in actions.items():
            self.console.print(f"  [{key}] {desc}", markup=False)

        return Prompt.ask("\nChoose action", choices=list(actions.keys()), default="i")

    def select_files(self, files: List[Path], prompt: str) -> List[Path]:
        """Let user select files from a group."""
        self.console.print("\nSelect files (space-separated numbers, 'all' or 'none'):")

        # Get suggested keeper if retention config exists
        suggested_keeper = None
        if self.retention_config:
            with suppress(ValueError):
                suggested_keeper = select_keeper(files, self.retention_config)

        # Display files
        for idx, file in enumerate(files, 1):
            marker = "(*)" if file == suggested_keeper else "   "
            self.console.print(f"  {idx}. {marker} {file}", markup=False)

        if suggested_keeper:
            self.console.print(
                "\n(*) Suggested file to keep based on retention criteria"
            )
            default_indices = [
                i for i, f in enumerate(files, 1) if f != suggested_keeper
            ]
            self.console.print(
                f"\nDefault action: move files {' '.join(map(str, default_indices))}"
            )

        while True:
            response = (
                Prompt.ask(
                    f"{prompt} (press Enter for default)"
                    if suggested_keeper
                    else prompt
                )
                .strip()
                .lower()
            )

            # Handle special cases
            if response == "" and suggested_keeper:
                return [f for f in files if f != suggested_keeper]
            if response == "all":
                return list(files)
            if response == "none":
                return []

            # Handle numeric selection
            try:
                indices = [int(i) - 1 for i in response.split()]
                selected = [files[i] for i in indices if 0 <= i < len(files)]
                if selected:
                    return selected
            except (ValueError, IndexError):
                pass

            self.console.print("[red]Invalid selection. Try again.[/red]")

    def confirm_action(self, action: str, files: List[Path]) -> bool:
        """Confirm an action before executing it."""
        self.console.print("\nSelected files:")
        for file in files:
            self.console.print(f"  • {file}")

        return Confirm.ask(f"\nConfirm {action}?", default=False)

    def show_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[red]Error: {message}[/red]")

    def show_success(self, message: str) -> None:
        """Display a success message."""
        self.console.print(f"[green]{message}[/green]")

    def get_file_preview(self, file: Path) -> str:
        """Get a truncated preview of file contents."""
        try:
            with file.open("r", encoding="utf-8") as f:
                # Read first few lines
                lines = []
                total_chars = 0
                for _ in range(self.preview_config.max_lines):
                    line = f.readline()
                    if not line:
                        break
                    # Strip trailing whitespace but keep leading whitespace
                    line = line.rstrip()
                    lines.append(line)
                    total_chars += len(line)

                preview = "\n".join(lines)

                # If we're over the character limit, truncate the last line
                if len(preview) > self.preview_config.max_chars:
                    marker = self.preview_config.truncation_marker
                    preview = (
                        preview[: (self.preview_config.max_chars - len(marker))]
                        + marker
                    )

                return preview
        except Exception as e:
            return f"[red]Error reading file: {e}[/red]"

    def show_detailed_info(
        self, files: List[Path], similarities: Dict[Tuple[Path, Path], float]
    ) -> None:
        """Display detailed information about files in a group."""
        # Create a table for file metadata
        metadata_table = Table(show_header=True, header_style="bold magenta")
        metadata_table.add_column("File", style="cyan")
        metadata_table.add_column("Size", justify="right", style="green")
        metadata_table.add_column("Created", justify="right", style="yellow")
        metadata_table.add_column("Modified", justify="right", style="yellow")
        metadata_table.add_column("Permissions", justify="center", style="blue")

        # Add file metadata rows
        for file in files:
            stats = file.stat()
            metadata_table.add_row(
                str(file),
                f"{stats.st_size:,} bytes",
                datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M"),
                datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M"),
                oct(stats.st_mode)[-3:],  # Last 3 digits of octal permissions
            )

        # Create a table for pairwise similarities
        sim_table = Table(show_header=True, header_style="bold magenta")
        sim_table.add_column("File 1", style="cyan")
        sim_table.add_column("File 2", style="cyan")
        sim_table.add_column("Similarity", justify="right", style="green")

        # Add similarity rows
        for (file1, file2), score in similarities.items():
            sim_table.add_row(str(file1), str(file2), f"{score:.2%}")

        # Create a table for file previews
        preview_table = Table(show_header=True, header_style="bold magenta")
        preview_table.add_column("File", style="cyan")
        preview_table.add_column("Preview", style="white")

        for file in files:
            preview = self.get_file_preview(file)
            preview_table.add_row(str(file), preview)

        # Display all tables in panels
        self.console.print(Panel(metadata_table, title="[bold blue]File Metadata"))
        self.console.print()
        self.console.print(Panel(sim_table, title="[bold blue]Similarity Scores"))
        self.console.print()
        self.console.print(Panel(preview_table, title="[bold blue]File Previews"))

    def display_move_preview(self, moves: List[MoveOperation]) -> None:
        """Display preview of move operations."""
        table = Table(title="Planned Moves")
        table.add_column("From")
        table.add_column("To")

        for move in moves:
            table.add_row(
                str(move.source),
                str(move.destination),
                style="dim" if self.move_config.dry_run else None,
            )

        self.console.print(table)
        if self.move_config.dry_run:
            self.console.print("[yellow]DRY RUN - No files will be moved[/yellow]")

    def show_preview(self, files: List[Path]) -> None:
        """Show preview of file contents."""
        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read(self.preview_config.max_chars)
                self.console.print(f"\n[bold]{file}[/bold]")
                self.console.print(content)
            except Exception as e:
                self.console.print(f"Error previewing {file}: {e}", style="red")

    def show_diff(self, files: List[Path]) -> None:
        """Show diff between files."""
        if len(files) != 2:
            self.console.print(
                "Diff is only available for exactly 2 files", style="yellow"
            )
            return

        try:
            from difflib import unified_diff

            with (
                open(files[0], "r", encoding="utf-8") as f1,
                open(files[1], "r", encoding="utf-8") as f2,
            ):
                diff = unified_diff(
                    f1.readlines(),
                    f2.readlines(),
                    fromfile=str(files[0]),
                    tofile=str(files[1]),
                )
                self.console.print("".join(diff))
        except Exception as e:
            self.console.print(f"Error showing diff: {e}", style="red")

    def create_moves(self, files: List[Path]) -> List[MoveOperation]:
        """Create move operations for the given files."""
        moves = prepare_moves(
            files=files,
            holding_dir=self.move_config.holding_dir,
            preserve_structure=self.move_config.preserve_structure,
            group_id=1,  # TODO: Use actual group ID
            retention_config=self.retention_config,
        )
        return moves if moves is not None else []  # Ensure we always return a list
