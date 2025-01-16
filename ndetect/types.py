"""Type definitions for ndetect."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, NewType, TypeAlias

import networkx as nx

# Type aliases for clarity
MinHashSignature = NewType("MinHashSignature", bytes)
SimilarityScore = NewType("SimilarityScore", float)

# A weighted graph where nodes are file paths and edges have similarity weights
SimilarityGraph: TypeAlias = "nx.Graph[Path]"


@dataclass
class SimilarGroup:
    """A group of similar files."""

    id: int
    files: List[Path]
    similarity: float


class Action(Enum):
    """Available actions for processing file groups."""

    KEEP = auto()  # Keep all files (k)
    DELETE = auto()  # Delete selected files (d)
    MOVE = auto()  # Move selected files (m)
    PREVIEW = auto()  # Preview file contents (p)
    SIMILARITIES = auto()  # Show similarities (s)
    QUIT = auto()  # Quit program (q)
