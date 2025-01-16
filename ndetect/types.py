"""Type definitions for ndetect."""

from dataclasses import dataclass
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
