"""Interactive UI components using rich."""

from typing import List, Dict, Tuple
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime

class InteractiveUI:
    def __init__(self) -> None:
        self.console = Console()
        
    def show_scan_progress(self, paths: List[str]) -> None:
        """Show progress while scanning files."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            progress.add_task("Scanning files...", total=None)
            
    def display_group(self, group_id: int, files: List[Path], similarity: float) -> None:
        """Display a group of similar files."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", justify="right", style="yellow")
        
        for file in files:
            stats = file.stat()
            table.add_row(
                str(file),
                f"{stats.st_size:,} bytes",
                f"{stats.st_mtime:.0f}"
            )
        
        similarity_desc = (
            f"~{similarity:.2%} similar" if len(files) == 2
            else f"~{similarity:.2%} avg. similarity"
        )
            
        self.console.print(Panel(
            table,
            title=f"[bold blue]Group {group_id} ({similarity_desc})",
            border_style="blue"
        ))
        
    def prompt_action(self) -> str:
        """Prompt user for action on current group."""
        self.console.print("\nAvailable actions:", style="bold")
        actions = {
            "k": "Keep all files",
            "d": "Delete duplicates",
            "m": "Move duplicates to holding directory",
            "i": "Show detailed information",
            "s": "Skip this group",
            "q": "Quit"
        }
        
        for key, desc in actions.items():
            self.console.print(f"  [{key}] {desc}")
            
        return Prompt.ask(
            "\nChoose action",
            choices=list(actions.keys()),
            default="s"
        )
        
    def select_files(self, files: List[Path], prompt: str) -> List[Path]:
        """Let user select files from a group."""
        self.console.print("\nSelect files (space-separated numbers, 'all' or 'none'):")
        for idx, file in enumerate(files, 1):
            self.console.print(f"  {idx}. {file}")
            
        while True:
            response = Prompt.ask(prompt).strip().lower()
            
            if response == "all":
                return list(files)
            elif response == "none":
                return []
                
            try:
                indices = [int(i) - 1 for i in response.split()]
                selected = [files[i] for i in indices if 0 <= i < len(files)]
                return selected
            except (ValueError, IndexError):
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
        
    def show_detailed_info(self, files: List[Path], similarities: Dict[Tuple[Path, Path], float]) -> None:
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
                oct(stats.st_mode)[-3:]  # Last 3 digits of octal permissions
            )
        
        # Create a table for pairwise similarities
        sim_table = Table(show_header=True, header_style="bold magenta")
        sim_table.add_column("File 1", style="cyan")
        sim_table.add_column("File 2", style="cyan")
        sim_table.add_column("Similarity", justify="right", style="green")
        
        # Add similarity rows
        for (file1, file2), score in similarities.items():
            sim_table.add_row(
                str(file1),
                str(file2),
                f"{score:.2%}"
            )
        
        # Create a table for file previews
        preview_table = Table(show_header=True, header_style="bold magenta")
        preview_table.add_column("File", style="cyan")
        preview_table.add_column("Preview", style="white")
        
        # Add file preview rows (first 5 lines of each file)
        for file in files:
            try:
                with file.open('r', encoding='utf-8') as f:
                    preview = '\n'.join(f.readlines()[:5])
                    if len(preview) > 200:  # Truncate long previews
                        preview = preview[:197] + "..."
            except Exception as e:
                preview = f"[red]Error reading file: {e}[/red]"
            preview_table.add_row(str(file), preview)
        
        # Display all tables in panels
        self.console.print(Panel(metadata_table, title="[bold blue]File Metadata"))
        self.console.print()
        self.console.print(Panel(sim_table, title="[bold blue]Similarity Scores"))
        self.console.print()
        self.console.print(Panel(preview_table, title="[bold blue]File Previews")) 