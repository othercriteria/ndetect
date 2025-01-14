from pathlib import Path
from datetime import datetime

from ndetect.similarity import SimilarityGraph
from ndetect.models import TextFile
from ndetect.minhash import create_minhash

def create_test_file(tmp_path: Path, name: str, content: str) -> TextFile:
    """Create a TextFile instance for testing."""
    file_path = tmp_path / name
    file_path.write_text(content)  # Actually write the content
    
    return TextFile(
        path=file_path,
        size=len(content),
        modified_time=datetime.now(),
        created_time=datetime.now(),
        signature=create_minhash(content)  # Use actual MinHash implementation
    )

def test_similarity_graph_empty() -> None:
    graph = SimilarityGraph()
    assert len(graph.get_groups()) == 0

def test_similarity_graph_single_file(tmp_path: Path) -> None:
    graph = SimilarityGraph()
    file = create_test_file(tmp_path, "test.txt", "hello world")
    graph.add_files([file])
    assert len(graph.get_groups()) == 0  # Single file should not form a group

def test_similarity_graph_similar_files(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")
    
    graph.add_files([file1, file2])
    groups = graph.get_groups()
    assert len(groups) == 1
    assert len(groups[0].files) == 2

def test_similarity_graph_dissimilar_files(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "completely different content")
    
    graph.add_files([file1, file2])
    assert len(graph.get_groups()) == 0  # Dissimilar files should not form a group

def test_similarity_graph_multiple_groups(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)
    
    # Create two groups of similar files
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")
    file3 = create_test_file(tmp_path, "test3.txt", "different content")
    file4 = create_test_file(tmp_path, "test4.txt", "different content")
    
    graph.add_files([file1, file2, file3, file4])
    groups = graph.get_groups()
    
    # Should have two groups
    assert len(groups) == 2
    # Each group should have two files
    group_sizes = [len(group.files) for group in groups]
    assert sorted(group_sizes) == [2, 2]

def test_similarity_graph_remove_files(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)
    
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")
    file3 = create_test_file(tmp_path, "test3.txt", "hello world")
    
    graph.add_files([file1, file2, file3])
    assert len(graph.get_groups()) == 1
    assert len(graph.get_groups()[0].files) == 3
    
    # Remove one file
    graph.remove_files([file1.path])
    assert len(graph.get_groups()) == 1
    assert len(graph.get_groups()[0].files) == 2

def test_similarity_graph_remove_nonexistent_file(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)
    
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")
    
    graph.add_files([file1, file2])
    
    # Try to remove a file that doesn't exist in the graph
    nonexistent = tmp_path / "nonexistent.txt"
    graph.remove_files([nonexistent])
    
    # Graph should remain unchanged
    assert len(graph.get_groups()) == 1
    assert len(graph.get_groups()[0].files) == 2

def test_similarity_graph_threshold(tmp_path: Path) -> None:
    # Test with different thresholds
    high_threshold = SimilarityGraph(threshold=0.9)
    low_threshold = SimilarityGraph(threshold=0.1)
    
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello there")  # Slightly different
    
    # With high threshold, files shouldn't be grouped
    high_threshold.add_files([file1, file2])
    assert len(high_threshold.get_groups()) == 0
    
    # With low threshold, files should be grouped
    low_threshold.add_files([file1, file2])
    assert len(low_threshold.get_groups()) == 1 