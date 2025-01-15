"""Models for representing text files and their properties."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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


@dataclass
class RetentionConfig:
    """Configuration for file retention criteria."""

    strategy: str = "newest"  # newest, oldest, shortest_path, largest, smallest
    priority_paths: List[str] = field(default_factory=list)
    priority_first: bool = True  # If True, priority paths override other criteria
