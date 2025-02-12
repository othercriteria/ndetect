"""Type definitions for ndetect."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Iterator, List, NewType, Optional, Tuple, TypeAlias

import networkx as nx

# Type aliases for clarity
MinHashSignature = NewType("MinHashSignature", bytes)
SimilarityScore = NewType("SimilarityScore", float)

# A weighted graph where nodes are file paths and edges have similarity weights
SimilarityGraph: TypeAlias = "nx.Graph[Path]"

# Common type aliases
JsonDict: TypeAlias = Dict[str, Any]
FileIterator: TypeAlias = Iterator[Path]
SimilarityPair: TypeAlias = Tuple[Path, Path, float]


@dataclass
class SimilarGroup:
    """A group of similar files."""

    id: int
    files: List[Path]
    similarity: float
    keeper: Optional[Path] = None  # Add keeper field


class Action(Enum):
    """Available actions for processing file groups."""

    NEXT = auto()  # Next group (n)
    DELETE = auto()  # Delete selected files (d)
    MOVE = auto()  # Move selected files (m)
    PREVIEW = auto()  # Preview file contents (p)
    SIMILARITIES = auto()  # Show similarities (s)
    HELP = auto()  # Show help (h)
    QUIT = auto()  # Quit program (q)
