"""Similarity graph implementation for near-duplicate detection."""

import itertools
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx
from datasketch import MinHash

from ndetect.minhash import similarity
from ndetect.models import TextFile
from ndetect.types import MinHashSignature, SimilarGroup
from ndetect.types import SimilarityGraph as SimilarityGraphType


class SimilarityGraph:
    """Graph representation of file similarities."""

    def __init__(self, threshold: float = 0.8) -> None:
        """Initialize similarity graph."""
        self.threshold = threshold
        self.graph: SimilarityGraphType = nx.Graph()
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
    ) -> Dict[Tuple[Path, Path], float]:
        """Compute pairwise similarities between files."""
        similarities = {}
        similarities.update(self._compute_new_file_similarities(files))
        similarities.update(self._compute_existing_node_similarities(files))
        return similarities

    def _compute_new_file_similarities(
        self, files: List[TextFile]
    ) -> Dict[Tuple[Path, Path], float]:
        """Compute similarities between new files."""
        similarities = {}
        for i, file1 in enumerate(files):
            if not file1.has_signature():
                continue
            sig1 = file1.signature
            if not isinstance(sig1, MinHash):
                continue

            for file2 in files[i + 1 :]:
                if not file2.has_signature():
                    continue
                sig2 = file2.signature
                if not isinstance(sig2, MinHash):
                    continue

                sim = similarity(sig1, sig2)
                if sim >= self.threshold:
                    similarities[(file1.path, file2.path)] = sim
        return similarities

    def _compute_existing_node_similarities(
        self, files: List[TextFile]
    ) -> Dict[Tuple[Path, Path], float]:
        """Compute similarities between new files and existing nodes."""
        similarities = {}
        for file in files:
            if not file.has_signature():
                continue
            sig1 = file.signature
            if not isinstance(sig1, MinHash):
                continue

            for node in self.graph.nodes():
                if self.graph.has_edge(file.path, node):
                    continue

                # Use first available edge weight as similarity
                for neighbor in self.graph.neighbors(node):
                    edge_sim = self.graph.edges[node, neighbor]["weight"]
                    if edge_sim >= self.threshold:
                        similarities[(file.path, node)] = edge_sim
                    break
        return similarities

    def add_files(self, files: List[TextFile]) -> None:
        """Add files to the similarity graph."""
        if not files:
            return

        # Add nodes for all files
        self.graph.add_nodes_from(f.path for f in files)

        # Compute similarities and add edges
        similarities = self._compute_pairwise_similarities(files)
        for (path1, path2), sim in similarities.items():
            self.graph.add_edge(path1, path2, weight=sim)

    def get_groups(self) -> List[SimilarGroup]:
        """Get all groups of similar files, sorted by similarity."""
        if not self.graph:
            return []

        # Find connected components (groups of similar files)
        groups = []
        for i, component in enumerate(nx.connected_components(self.graph), 1):
            files = sorted(component)  # Sort for consistent ordering
            if len(files) < 2:
                continue

            # Calculate average similarity for the group
            similarities = []
            for f1, f2 in itertools.combinations(files, 2):
                if self.graph.has_edge(f1, f2):
                    similarities.append(self.graph.edges[f1, f2]["weight"])
            avg_similarity = sum(similarities) / len(similarities)

            groups.append(
                SimilarGroup(
                    id=i,
                    files=files,
                    similarity=avg_similarity,
                )
            )

        # Sort groups by similarity (highest first)
        return sorted(groups, key=lambda g: g.similarity, reverse=True)

    def remove_files(self, files: List[Path]) -> None:
        """Remove files from the graph."""
        if not files:
            return

        existing_files = [f for f in files if f in self.graph]
        self.graph.remove_nodes_from(existing_files)
        # Clean up cache
        for file in existing_files:
            self._signature_cache.pop(file, None)

    def get_group_similarities(
        self, group_files: List[Path]
    ) -> Dict[Tuple[Path, Path], float]:
        """Get pairwise similarities for files in a group."""
        similarities = {}
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
