"""Interactive UI components using rich."""

from typing import List, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

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
            # Actual scanning happens in the caller
            
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
            
        self.console.print(Panel(
            table,
            title=f"[bold blue]Group {group_id} (Similarity: {similarity:.2%})",
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