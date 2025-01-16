from rich.console import Console
from rich.panel import Panel

from ndetect.logging import StructuredLogger, setup_logging

logger: StructuredLogger = setup_logging(None)


class NDetectError(Exception):
    """Base exception class for ndetect."""

    pass


class FileOperationError(NDetectError):
    """Raised when file operations (read/write/move/delete) fail."""

    def __init__(self, message: str, path: str, operation: str):
        self.path = path
        self.operation = operation
        super().__init__(f"{operation} failed for {path}: {message}")


class DiskSpaceError(FileOperationError):
    """Raised when there's insufficient disk space."""

    def __init__(self, path: str, required_bytes: int, available_bytes: int):
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        message = (
            f"Need {required_bytes:,} bytes, but only {available_bytes:,} available"
        )
        super().__init__(message, path, "write")


class PermissionError(FileOperationError):
    """Raised when permission is denied for file operations."""

    def __init__(self, path: str, operation: str):
        super().__init__("Permission denied", path, operation)


class InvalidFileError(NDetectError):
    """Raised when a file is invalid or corrupted."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Invalid file {path}: {reason}")


def handle_error(console: Console, error: Exception) -> int:
    """Handle errors with structured logging."""
    logger.error_with_fields(
        "Operation failed",
        error_type=type(error).__name__,
        error_message=str(error),
        operation="error_handling",
    )

    if isinstance(error, DiskSpaceError):
        console.print(
            Panel(
                f"[red]Not enough disk space: {error}[/red]",
                title="Error",
                border_style="red",
            )
        )
    elif isinstance(error, PermissionError):
        console.print(
            Panel(
                f"[red]Permission denied: {error}[/red]",
                title="Error",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]Operation failed: {error}[/red]",
                title="Error",
                border_style="red",
            )
        )
    return 1


def format_error_message(error: Exception) -> str:
    """Format error message for display."""
    if isinstance(error, DiskSpaceError):
        return (
            f"[red]Insufficient disk space[/red]\n"
            f"Required: {error.required_bytes:,} bytes\n"
            f"Available: {error.available_bytes:,} bytes\n"
            f"Path: {error.path}"
        )
    elif isinstance(error, PermissionError):
        return (
            f"[red]Permission denied[/red]\n"
            f"Operation: {error.operation}\n"
            f"Path: {error.path}"
        )
    elif isinstance(error, FileOperationError):
        return (
            f"[red]File operation failed[/red]\n"
            f"Operation: {error.operation}\n"
            f"Path: {error.path}"
        )
    return f"[red]Error: {str(error)}[/red]"
