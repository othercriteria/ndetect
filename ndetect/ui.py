"""Interactive UI components using rich."""

from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime

class InteractiveUI:
    def __init__(
        self,
        console: Optional[Console] = None,
        preview_config: Optional[Dict[str, Any]] = None
    ) -> None:
        self.console = console or Console()
        # Use provided config or defaults
        self.preview_config = preview_config or {
            'max_chars': 100,
            'max_lines': 3,
            'truncation_marker': '...'
        }
        
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
        self.console.print(f"\n[bold blue]Group {group_id}[/bold blue]")
        self.console.print(f"Average similarity: [green]{similarity:.2%}[/green]")
        
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
                datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M")
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
            "q": "Quit"
        }
        
        for key, desc in actions.items():
            self.console.print(f"  [{key}] {desc}")
            
        return Prompt.ask(
            "\nChoose action",
            choices=list(actions.keys()),
            default="i"
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
        
    def get_file_preview(self, file: Path) -> str:
        """Get a truncated preview of file contents."""
        try:
            with file.open('r', encoding='utf-8') as f:
                # Read first few lines
                lines = []
                total_chars = 0
                for _ in range(self.preview_config['max_lines']):
                    line = f.readline()
                    if not line:
                        break
                    # Strip trailing whitespace but keep leading whitespace
                    line = line.rstrip()
                    lines.append(line)
                    total_chars += len(line)
                    
                preview = '\n'.join(lines)
                
                # If we're over the character limit, truncate the last line
                if len(preview) > self.preview_config['max_chars']:
                    marker = self.preview_config['truncation_marker']
                    preview = preview[:(self.preview_config['max_chars'] - len(marker))] + marker
                
                return preview
        except Exception as e:
            return f"[red]Error reading file: {e}[/red]"

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
        
        for file in files:
            preview = self.get_file_preview(file)
            preview_table.add_row(str(file), preview)
        
        # Display all tables in panels
        self.console.print(Panel(metadata_table, title="[bold blue]File Metadata"))
        self.console.print()
        self.console.print(Panel(sim_table, title="[bold blue]Similarity Scores"))
        self.console.print()
        self.console.print(Panel(preview_table, title="[bold blue]File Previews")) 