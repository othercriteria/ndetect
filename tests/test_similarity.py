from datetime import datetime
from pathlib import Path

import networkx as nx
import pytest
from datasketch import MinHash

from ndetect.models import TextFile
from ndetect.signatures import compute_minhash_from_chunks
from ndetect.similarity import SimilarityGraph


def create_test_file(tmp_path: Path, name: str, content: str) -> TextFile:
    """Create a TextFile instance for testing."""
    file_path = tmp_path / name
    file_path.write_text(content)

    text_file = TextFile(
        path=file_path,
        size=len(content),
        modified_time=datetime.now(),
        created_time=datetime.now(),
    )
    # Create signature from content bytes directly
    sig = compute_minhash_from_chunks([content.encode("utf-8")])
    if not isinstance(sig, MinHash):
        pytest.fail("Failed to create MinHash signature")
    text_file.signature = sig
    return text_file


def test_similarity_graph_empty() -> None:
    graph = SimilarityGraph()
    assert isinstance(graph.graph, nx.Graph)
    assert len(graph.get_groups()) == 0


def test_similarity_graph_single_file(tmp_path: Path) -> None:
    graph = SimilarityGraph()
    file = create_test_file(tmp_path, "test.txt", "hello world")
    graph.add_files([file])
    assert isinstance(graph.graph, nx.Graph)
    assert len(graph.get_groups()) == 0  # Single file should not form a group


def test_similarity_graph_similar_files(tmp_path: Path) -> None:
    """Test that similar files are grouped together."""
    file1 = create_test_file(tmp_path, "file1.txt", "This is a test document")
    file2 = create_test_file(tmp_path, "file2.txt", "This is a test document too")

    graph = SimilarityGraph(threshold=0.7)  # Lower threshold for test reliability
    graph.add_files([file1, file2])

    groups = list(graph.get_groups())
    assert len(groups) == 1, "Expected one group of similar files"
    group = groups[0]
    assert len(group.files) == 2, "Expected two files in the group"
    assert group.similarity >= 0.7, "Expected similarity above threshold"


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
    initial_groups = graph.get_groups()
    assert len(initial_groups) == 1
    assert len(initial_groups[0].files) == 3

    graph.remove_files([file1.path])
    updated_groups = graph.get_groups()
    assert len(updated_groups) == 1
    assert len(updated_groups[0].files) == 2
    assert file1.path not in updated_groups[0].files


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


def test_similarity_graph_batch_processing(tmp_path: Path) -> None:
    """Test that batch processing correctly groups identical files."""
    # Create identical content files in batches
    content = "identical content"
    files = [create_test_file(tmp_path, f"test{i}.txt", content) for i in range(4)]

    graph = SimilarityGraph(threshold=0.8)
    # Add files in two batches
    graph.add_files(files[:2])
    graph.add_files(files[2:])

    groups = list(graph.get_groups())
    assert len(groups) == 1, "Expected all identical files in one group"
    group = groups[0]
    assert len(group.files) == 4, "Expected all four files in the group"
    assert group.similarity == 1.0, "Expected perfect similarity for identical content"


def test_similarity_graph_different_files(tmp_path: Path) -> None:
    """Test that different files are not grouped."""
    file1 = create_test_file(tmp_path, "test1.txt", "completely different content")
    file2 = create_test_file(tmp_path, "test2.txt", "totally unrelated text here")

    graph = SimilarityGraph()
    graph.add_files([file1, file2])

    groups = list(graph.get_groups())
    assert len(groups) == 0, "Expected no groups for different files"


def test_similarity_graph_keep_group(tmp_path: Path) -> None:
    graph = SimilarityGraph(threshold=0.8)

    # Create two groups of similar files
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")
    file3 = create_test_file(tmp_path, "test3.txt", "different content")
    file4 = create_test_file(tmp_path, "test4.txt", "different content")

    graph.add_files([file1, file2, file3, file4])
    initial_groups = graph.get_groups()
    assert len(initial_groups) == 2

    # Keep one group
    graph.remove_group(initial_groups[0].files)
    updated_groups = graph.get_groups()
    assert len(updated_groups) == 1
    # Files from kept group should not appear in any remaining groups
    kept_files = set(initial_groups[0].files)
    assert not any(f in kept_files for f in updated_groups[0].files)


def test_similarity_graph_sorting(tmp_path: Path) -> None:
    """Test that groups are returned in descending order of similarity."""
    graph = SimilarityGraph(threshold=0.5)  # Low threshold to ensure all groups form

    # Create distinct pairs with different internal similarities
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")  # Identical pair
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")  # sim = 1.0

    file3 = create_test_file(
        tmp_path, "test3.txt", "python programming"
    )  # Similar pair
    file4 = create_test_file(tmp_path, "test4.txt", "python programmer")  # sim ≈ 0.7

    file5 = create_test_file(tmp_path, "test5.txt", "red apple")  # Less similar pair
    file6 = create_test_file(tmp_path, "test6.txt", "reed apple")  # sim ≈ 0.6

    graph.add_files([file1, file2, file3, file4, file5, file6])
    groups = graph.get_groups()

    assert len(groups) == 3  # Should have three distinct groups
    # Verify descending order with some tolerance for MinHash approximation
    for i in range(len(groups) - 1):
        assert groups[i].similarity >= groups[i + 1].similarity


def test_similarity_graph_new_files(tmp_path: Path) -> None:
    """Test similarity computation between new files."""
    file1 = create_test_file(tmp_path, "file1.txt", "This is a test document")
    file2 = create_test_file(tmp_path, "file2.txt", "This is a test document too")
    file3 = create_test_file(tmp_path, "file3.txt", "completely different content")

    graph = SimilarityGraph(threshold=0.7)
    graph.add_files([file1, file2, file3])

    groups = list(graph.get_groups())
    assert len(groups) == 1, "Expected one group of similar files"
    assert len(groups[0].files) == 2, "Expected two similar files grouped"
    assert groups[0].similarity >= 0.7, "Expected similarity above threshold"


def test_similarity_graph_existing_nodes(tmp_path: Path) -> None:
    """Test similarity computation with existing nodes."""
    # First batch
    file1 = create_test_file(tmp_path, "file1.txt", "identical content")
    file2 = create_test_file(tmp_path, "file2.txt", "identical content")

    graph = SimilarityGraph(threshold=0.8)
    graph.add_files([file1, file2])

    # Second batch
    file3 = create_test_file(tmp_path, "file3.txt", "identical content")
    graph.add_files([file3])

    groups = list(graph.get_groups())
    assert len(groups) == 1, "Expected one group connecting all batches"
    assert len(groups[0].files) == 3, "Expected all three identical files grouped"
    assert groups[0].similarity == 1.0, "Expected perfect similarity when identical"


def test_similarity_graph_invalid_signatures(tmp_path: Path) -> None:
    """Test handling of files with invalid or missing signatures."""
    file1 = create_test_file(tmp_path, "file1.txt", "content")
    file2 = create_test_file(tmp_path, "file2.txt", "content")
    file2.signature = None  # Invalidate signature

    graph = SimilarityGraph()
    graph.add_files([file1, file2])

    groups = list(graph.get_groups())
    assert len(groups) == 0, "Expected no groups with invalid signatures"


def test_similarity_graph_threshold_filtering(tmp_path: Path) -> None:
    """Test that similarities below threshold are filtered out."""
    file1 = create_test_file(tmp_path, "file1.txt", "some shared words here")
    file2 = create_test_file(tmp_path, "file2.txt", "some shared words there")
    file3 = create_test_file(tmp_path, "file3.txt", "completely different")

    # Test with different thresholds
    high_threshold = SimilarityGraph(threshold=0.9)
    low_threshold = SimilarityGraph(threshold=0.3)

    high_threshold.add_files([file1, file2])
    low_threshold.add_files([file1, file2, file3])

    high_groups = list(high_threshold.get_groups())
    low_groups = list(low_threshold.get_groups())

    assert len(high_groups) == 0, "Expected no groups with high threshold"
    assert len(low_groups) == 1, "Expected one group with low threshold"
    if low_groups:
        assert len(low_groups[0].files) == 2, "Expected only similar files grouped"
