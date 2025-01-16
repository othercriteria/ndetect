"""Similarity graph implementation for near-duplicate detection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx

from ndetect.minhash import similarity
from ndetect.models import TextFile
from ndetect.types import MinHashSignature
from ndetect.types import SimilarityGraph as SimilarityGraphType


@dataclass
class Group:
    """A group of similar files."""

    id: int
    files: List[Path]
    similarity: float


class SimilarityGraph:
    """Graph representation of file similarities."""

    def __init__(self, threshold: float = 0.8) -> None:
        self.graph: SimilarityGraphType = nx.Graph()
        self.threshold = threshold
        # Cache for MinHash signatures
        self._signature_cache: Dict[Path, MinHashSignature] = {}
        self._next_group_id = 1

    def _get_signature(self, file: TextFile) -> Optional[MinHashSignature]:
        """Get cached signature or compute and cache it."""
        if file.path not in self._signature_cache and file.signature is not None:
            self._signature_cache[file.path] = MinHashSignature(
                file.signature.digest().tobytes()
            )
        return self._signature_cache.get(file.path)

    def _compute_pairwise_similarities(
        self, files: List[TextFile]
    ) -> List[Tuple[Path, Path, float]]:
        """Compute pairwise similarities between files."""
        similarities: List[Tuple[Path, Path, float]] = []

        for i, file1 in enumerate(files):
            if not file1.has_signature() or file1.signature is None:
                continue

            # Convert MinHash to bytes for signature
            sig1 = MinHashSignature(file1.signature.digest().tobytes())
            self._signature_cache[file1.path] = sig1

            # Compare with existing files in graph
            for existing_path, existing_sig in self._signature_cache.items():
                if existing_path == file1.path:
                    continue

                sim = similarity(sig1, existing_sig)
                if sim >= self.threshold:
                    similarities.append((file1.path, existing_path, sim))

            # Compare with remaining new files
            for file2 in files[i + 1 :]:
                if not file2.has_signature() or file2.signature is None:
                    continue

                # Convert MinHash to bytes for signature
                sig2 = MinHashSignature(file2.signature.digest().tobytes())
                self._signature_cache[file2.path] = sig2

                sim = similarity(sig1, sig2)
                if sim >= self.threshold:
                    similarities.append((file1.path, file2.path, sim))

        return similarities

    def add_files(self, files: List[TextFile]) -> None:
        """Add files to the similarity graph."""
        if not files:
            return

        # Add nodes first
        self.graph.add_nodes_from(f.path for f in files)

        # Compute similarities and add edges
        similarities = self._compute_pairwise_similarities(files)
        for path1, path2, sim in similarities:
            self.graph.add_edge(path1, path2, weight=sim)

    def get_groups(self) -> List[Group]:
        """Get all groups of similar files."""
        groups: List[Group] = []

        # Find connected components (groups of similar files)
        components = list(nx.connected_components(self.graph))

        for component in components:
            if len(component) < 2:
                continue

            # Calculate average similarity for the group
            similarities = []
            files = list(component)
            for i, file1 in enumerate(files):
                for file2 in files[i + 1 :]:
                    if self.graph.has_edge(file1, file2):
                        similarities.append(self.graph.edges[file1, file2]["weight"])

            avg_similarity = (
                sum(similarities) / len(similarities) if similarities else 0.0
            )

            groups.append(
                Group(
                    id=self._next_group_id,
                    files=list(component),
                    similarity=avg_similarity,
                )
            )
            self._next_group_id += 1

        return groups

    def remove_files(self, files: List[Path]) -> None:
        """Remove files from the graph."""
        if not files:
            return

        # Remove only existing nodes
        existing_files = [f for f in files if f in self.graph]
        self.graph.remove_nodes_from(existing_files)
        # Clean up cache
        for file in existing_files:
            self._signature_cache.pop(file, None)

    def get_group_similarities(
        self, group_files: List[Path]
    ) -> Dict[Tuple[Path, Path], float]:
        """Get pairwise similarities for files in a group."""
        similarities: Dict[Tuple[Path, Path], float] = {}

        for i, file1 in enumerate(group_files):
            for file2 in group_files[i + 1 :]:
                if self.graph.has_edge(file1, file2):
                    similarities[(file1, file2)] = self.graph.edges[file1, file2][
                        "weight"
                    ]

        return similarities

    def remove_group(self, files: List[Path]) -> None:
        """Remove all edges between files in a group, effectively dissolving it."""
        if not files:
            return

        # Remove edges between all files in the group
        for i, file1 in enumerate(files):
            for file2 in files[i + 1 :]:
                if self.graph.has_edge(file1, file2):
                    self.graph.remove_edge(file1, file2)
