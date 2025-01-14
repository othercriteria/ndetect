"""Similarity graph implementation for near-duplicate detection."""

from typing import List
from pathlib import Path
import networkx as nx
from dataclasses import dataclass

from ndetect.models import TextFile
from ndetect.types import MinHashSignature, SimilarityScore
from ndetect.minhash import similarity

@dataclass
class DuplicateGroup:
    """A group of similar files."""
    id: int
    files: List[Path]
    similarity: SimilarityScore  # Average similarity within group

class SimilarityGraph:
    """Graph representation of file similarities."""
    
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.graph: nx.Graph[Path] = nx.Graph()
        
    def add_files(self, files: List[TextFile]) -> None:
        """Add files to the graph, creating edges for similar pairs."""
        if not files:
            return
            
        # Add all files as nodes
        for file in files:
            if not isinstance(file, TextFile):
                raise TypeError(f"Expected TextFile object, got {type(file)}")
            if file.signature is None:
                continue
            self.graph.add_node(file.path)
        
        # Add edges between similar files
        for i, file1 in enumerate(files):
            for file2 in files[i + 1:]:
                if file1.signature is None or file2.signature is None:
                    continue
                sim_score = similarity(
                    MinHashSignature(file1.signature.digest().tobytes()),
                    MinHashSignature(file2.signature.digest().tobytes())
                )
                if sim_score >= self.threshold:
                    self.graph.add_edge(file1.path, file2.path, weight=sim_score)
    
    def get_groups(self) -> List[DuplicateGroup]:
        """Get groups of similar files using connected components."""
        groups: List[DuplicateGroup] = []
        
        for i, component in enumerate(nx.connected_components(self.graph), 1):
            if len(component) > 1:  # Only include groups with duplicates
                files = sorted(component)  # Sort for consistent ordering
                # Calculate average similarity within group
                similarities = [
                    self.graph.edges[u, v]["weight"]  # Access edge data directly
                    for u in component
                    for v in component
                    if u < v and self.graph.has_edge(u, v)
                ]
                avg_similarity = sum(similarities) / len(similarities)
                groups.append(DuplicateGroup(i, files, avg_similarity))
        
        return groups
    
    def remove_files(self, files: List[Path]) -> None:
        """Remove files from the graph."""
        if not files:
            return
            
        # Remove only existing nodes
        existing_files = [f for f in files if f in self.graph]
        self.graph.remove_nodes_from(existing_files) 