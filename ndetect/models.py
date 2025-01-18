"""Models for representing text files and their properties."""

from argparse import Namespace
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from datasketch import MinHash

from ndetect.minhash import compute_signature


@dataclass
class TextFile:
    """Represents a text file with its metadata and signature."""

    path: Path
    size: int
    modified_time: datetime
    created_time: datetime
    signature: Optional[MinHash] = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        compute_minhash: bool = True,
        num_perm: int = 128,
        shingle_size: int = 5,
    ) -> "TextFile":
        """Create a TextFile instance from a path."""
        stat = path.stat()
        instance = cls(
            path=path,
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            created_time=datetime.fromtimestamp(stat.st_ctime),
        )

        if compute_minhash:
            instance.signature = compute_signature(
                path, num_perm=num_perm, shingle_size=shingle_size
            )

        return instance

    @property
    def extension(self) -> str:
        """Get the file extension (lowercase)."""
        return self.path.suffix.lower()

    @property
    def name(self) -> str:
        """Get the file name."""
        return self.path.name

    @property
    def parent(self) -> Path:
        """Get the parent directory."""
        return self.path.parent

    def has_signature(self) -> bool:
        """Check if the file has a MinHash signature."""
        return self.signature is not None

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return f"{self.path} ({self.size} bytes, modified {self.modified_time})"


@dataclass
class MoveConfig:
    """Configuration for move operations."""

    holding_dir: Path
    preserve_structure: bool = True
    dry_run: bool = False


@dataclass
class PreviewConfig:
    """Configuration for file preview display."""

    max_chars: int = 100
    max_lines: int = 3
    truncation_marker: str = "..."

    def __post_init__(self) -> None:
        """Validate numeric constraints."""
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if self.max_lines <= 0:
            raise ValueError("max_lines must be positive")


@dataclass
class RetentionConfig:
    """Configuration for file retention criteria."""

    strategy: str = "newest"  # newest, oldest, shortest_path, largest, smallest
    priority_paths: List[str] = field(default_factory=list)
    priority_first: bool = True  # If True, priority paths override other criteria

    VALID_STRATEGIES = {"newest", "oldest", "shortest_path", "largest", "smallest"}

    def __post_init__(self) -> None:
        """Validate strategy value."""
        if self.strategy not in self.VALID_STRATEGIES:
            strategies = ", ".join(sorted(self.VALID_STRATEGIES))
            raise ValueError(f"Invalid strategy. Must be one of: {strategies}")


@dataclass
class FileAnalyzerConfig:
    """Configuration for file analysis."""

    min_printable_ratio: float = 0.8
    num_perm: int = 128
    shingle_size: int = 5
    allowed_extensions: Optional[Set[str]] = None
    follow_symlinks: bool = True
    skip_empty: bool = True
    max_workers: Optional[int] = None
    max_symlink_depth: int = 10  # New field with default matching resolve_symlink
    base_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        """Validate configuration and set defaults."""
        if self.allowed_extensions is None:
            self.allowed_extensions = {".txt", ".md", ".log", ".csv"}

        if not 0 <= self.min_printable_ratio <= 1:
            raise ValueError("min_printable_ratio must be between 0 and 1")

        if self.num_perm <= 0:
            raise ValueError("num_perm must be positive")

        if self.shingle_size <= 0:
            raise ValueError("shingle_size must be positive")

        if self.max_workers is not None and self.max_workers <= 0:
            raise ValueError("max_workers must be positive")

        if self.max_symlink_depth <= 0:
            raise ValueError("max_symlink_depth must be positive")


@dataclass
class CLIConfig:
    """Configuration for CLI operation."""

    paths: list[str]
    mode: str
    threshold: float
    base_dir: Path = field(default_factory=Path.cwd)
    holding_dir: Path = field(default_factory=lambda: Path("duplicates"))
    log_file: Path = field(default_factory=lambda: Path("ndetect.log"))
    verbose: bool = False
    min_printable_ratio: float = 0.7
    num_perm: int = 128
    shingle_size: int = 3
    follow_symlinks: bool = False
    max_workers: Optional[int] = None
    dry_run: bool = False
    max_symlink_depth: int = 10
    skip_empty: bool = True
    preview_chars: int = 100
    preview_lines: int = 3
    flat_holding: bool = False
    retention_strategy: str = "newest"
    priority_paths: List[str] = field(default_factory=list)
    priority_first: bool = False

    @classmethod
    def from_args(cls, args: Namespace) -> "CLIConfig":
        """Create a CLIConfig from parsed command line arguments."""
        return cls(
            paths=args.paths,
            mode=args.mode,
            threshold=args.threshold,
            base_dir=Path(args.base_dir) if args.base_dir else Path.cwd(),
            holding_dir=Path(args.holding_dir)
            if args.holding_dir
            else Path("duplicates"),
            log_file=Path(args.log_file) if args.log_file else Path("ndetect.log"),
            verbose=args.verbose,
            min_printable_ratio=args.min_printable_ratio,
            num_perm=args.num_perm,
            shingle_size=args.shingle_size,
            follow_symlinks=args.follow_symlinks,
            max_workers=args.max_workers,
            dry_run=args.dry_run,
            max_symlink_depth=args.max_symlink_depth,
            skip_empty=not args.include_empty,
            preview_chars=args.preview_chars,
            preview_lines=args.preview_lines,
            flat_holding=args.flat_holding,
            retention_strategy=args.retention,
            priority_paths=args.priority_paths or [],
            priority_first=args.priority_first,
        )

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.paths:
            raise ValueError("At least one path must be provided")
        if self.threshold <= 0 or self.threshold > 1:
            raise ValueError("Threshold must be between 0 and 1")
        if self.min_printable_ratio <= 0 or self.min_printable_ratio > 1:
            raise ValueError("min_printable_ratio must be between 0 and 1")

    @property
    def retention_config(self) -> Optional[RetentionConfig]:
        """Create RetentionConfig from settings."""
        return RetentionConfig(
            strategy=self.retention_strategy,
            priority_paths=self.priority_paths or [],
            priority_first=self.priority_first,
        )

    @property
    def move_config(self) -> MoveConfig:
        """Create MoveConfig from settings."""
        return MoveConfig(
            holding_dir=self.holding_dir,
            preserve_structure=not self.flat_holding,
            dry_run=self.dry_run,
        )

    @property
    def preview_config(self) -> PreviewConfig:
        """Create PreviewConfig from settings."""
        return PreviewConfig(
            max_chars=self.preview_chars,
            max_lines=self.preview_lines,
        )
