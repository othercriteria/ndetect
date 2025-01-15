from datetime import datetime
from pathlib import Path

import networkx as nx

from ndetect.minhash import create_minhash
from ndetect.models import TextFile
from ndetect.similarity import SimilarityGraph


def create_test_file(tmp_path: Path, name: str, content: str) -> TextFile:
    """Create a TextFile instance for testing."""
    file_path = tmp_path / name
    file_path.write_text(content)  # Actually write the content

    return TextFile(
        path=file_path,
        size=len(content),
        modified_time=datetime.now(),
        created_time=datetime.now(),
        signature=create_minhash(content),  # Use actual MinHash implementation
    )


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


def test_similarity_graph_cache(tmp_path: Path) -> None:
    """Test that signature caching works correctly."""
    graph = SimilarityGraph(threshold=0.8)

    # Create two identical files
    file1 = create_test_file(tmp_path, "test1.txt", "hello world")
    file2 = create_test_file(tmp_path, "test2.txt", "hello world")

    # Add files and check cache
    graph.add_files([file1, file2])
    assert len(graph._signature_cache) == 2

    # Remove one file and verify cache cleanup
    graph.remove_files([file1.path])
    assert len(graph._signature_cache) == 1
    assert file1.path not in graph._signature_cache
    assert file2.path in graph._signature_cache


def test_similarity_graph_batch_size(tmp_path: Path) -> None:
    """Test that batching doesn't affect results."""
    graph1 = SimilarityGraph(threshold=0.8)
    graph2 = SimilarityGraph(threshold=0.8)

    # Create several similar files
    files = [
        create_test_file(tmp_path, f"test{i}.txt", "hello world") for i in range(5)
    ]

    # Add files with different batch sizes
    graph1.add_files(files, batch_size=2)
    graph2.add_files(files, batch_size=3)

    # Results should be identical
    groups1 = graph1.get_groups()
    groups2 = graph2.get_groups()
    assert len(groups1) == len(groups2)
    assert all(g1.files == g2.files for g1, g2 in zip(groups1, groups2))


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
