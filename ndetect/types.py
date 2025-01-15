"""Type definitions for ndetect."""

from pathlib import Path
from typing import NewType, TypeAlias

import networkx as nx

# Type aliases for clarity
MinHashSignature = NewType("MinHashSignature", bytes)
SimilarityScore = NewType("SimilarityScore", float)

# A weighted graph where nodes are file paths and edges have similarity weights
SimilarityGraph: TypeAlias = "nx.Graph[Path]"
