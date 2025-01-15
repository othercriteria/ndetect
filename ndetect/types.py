"""Type definitions for ndetect."""

from typing import NewType, TypeAlias
from pathlib import Path
import networkx as nx

# Type aliases for clarity
MinHashSignature = NewType('MinHashSignature', bytes)
SimilarityScore = NewType('SimilarityScore', float)

# A weighted graph where nodes are file paths and edges have similarity weights
SimilarityGraph: TypeAlias = 'nx.Graph[Path]' 