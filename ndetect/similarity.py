"""Similarity graph implementation for near-duplicate detection."""

from typing import List, Dict, Tuple, Optional
from pathlib import Path
import networkx as nx
from dataclasses import dataclass

from ndetect.models import TextFile
from ndetect.types import MinHashSignature, SimilarityScore, SimilarityGraph as SimilarityGraphType
from ndetect.minhash import similarity

@dataclass
class DuplicateGroup:
    """A group of similar files."""
    id: int
    files: List[Path]
    similarity: SimilarityScore  # Average similarity within group

class SimilarityGraph:
    """Graph representation of file similarities."""
    
    def __init__(self, threshold: float = 0.85) -> None:
        self.graph: SimilarityGraphType = nx.Graph()
        self.threshold = threshold
        # Cache for MinHash signatures
        self._signature_cache: Dict[Path, MinHashSignature] = {}
        
    def _get_signature(self, file: TextFile) -> Optional[MinHashSignature]:
        """Get cached signature or compute and cache it."""
        if file.path not in self._signature_cache and file.signature is not None:
            self._signature_cache[file.path] = MinHashSignature(
                file.signature.digest().tobytes()
            )
        return self._signature_cache.get(file.path)
    
    def add_files(self, files: List[TextFile], batch_size: int = 1000) -> None:
        """Add files to the graph, with optional batching for progress display."""
        if not files:
            return
        
        # Process files in batches
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            
            # Add nodes and edges for the batch
            for file in batch:
                if not isinstance(file, TextFile):
                    raise TypeError(f"Expected TextFile object, got {type(file)}")
                if file.signature is None:
                    continue
                
                self.graph.add_node(file.path)
                sig1 = self._get_signature(file)
                if sig1 is None:
                    continue
                
                # Compare with all other files (including those outside batch)
                for other in files:
                    if other.path == file.path or other.signature is None:
                        continue
                    
                    sig2 = self._get_signature(other)
                    if sig2 is None:
                        continue
                    
                    sim_score = similarity(sig1, sig2)
                    if sim_score >= self.threshold:
                        self.graph.add_edge(file.path, other.path, weight=sim_score)
    
    def get_groups(self) -> List[DuplicateGroup]:
        """Get groups of similar files using connected components, sorted by similarity."""
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
        
        # Sort groups by similarity in descending order
        return sorted(groups, key=lambda g: g.similarity, reverse=True)
    
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
    
    def get_group_similarities(self, group_files: List[Path]) -> Dict[Tuple[Path, Path], float]:
        """Get pairwise similarities for files in a group."""
        similarities: Dict[Tuple[Path, Path], float] = {}
        
        for i, file1 in enumerate(group_files):
            for file2 in group_files[i + 1:]:
                if self.graph.has_edge(file1, file2):
                    similarities[(file1, file2)] = self.graph.edges[file1, file2]["weight"]
        
        return similarities 
    
    def remove_group(self, files: List[Path]) -> None:
        """Remove all edges between files in a group, effectively dissolving it."""
        if not files:
            return
        
        # Remove edges between all files in the group
        for i, file1 in enumerate(files):
            for file2 in files[i + 1:]:
                if self.graph.has_edge(file1, file2):
                    self.graph.remove_edge(file1, file2) 