from datetime import datetime
from pathlib import Path
from typing import Callable

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


def test_similarity_graph_similar_files(
    similarity_graph: SimilarityGraph,
    create_text_file: Callable[[str, str], TextFile],
) -> None:
    file1 = create_text_file("test1.txt", "hello world")
    file2 = create_text_file("test2.txt", "hello world")

    similarity_graph.add_files([file1, file2])
    groups = similarity_graph.get_groups()
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


def test_similarity_graph_cache(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test that signature caching works correctly."""
    graph = SimilarityGraph(threshold=0.8)

    # Create two identical files
    file1 = TextFile.from_path(create_file_with_content("test1.txt", "hello world"))
    file2 = TextFile.from_path(create_file_with_content("test2.txt", "hello world"))

    # Add files and check cache
    graph.add_files([file1, file2])
    assert len(graph._signature_cache) == 2

    # Remove one file and verify cache cleanup
    graph.remove_files([file1.path])
    assert len(graph._signature_cache) == 1
    assert file1.path not in graph._signature_cache
    assert file2.path in graph._signature_cache


def test_similarity_graph_batch_processing(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test processing files in batches."""
    graph = SimilarityGraph(threshold=0.8)

    # Create test files
    files = []
    for i in range(4):
        path = create_file_with_content(f"test{i}.txt", "hello world")
        text_file = TextFile.from_path(path, compute_minhash=True)
        files.append(text_file)

    # Process files in two batches
    first_batch = files[:2]
    second_batch = files[2:]

    graph.add_files(first_batch)
    assert len(graph.get_groups()) == 1  # First group formed

    graph.add_files(second_batch)
    groups = graph.get_groups()
    assert len(groups) == 1  # All files in one group
    assert len(groups[0].files) == 4  # All files included


def test_similarity_graph_different_content(
    create_file_with_content: Callable[[str, str], Path],
) -> None:
    """Test that different content creates separate groups."""
    # Use a higher threshold to ensure different content creates separate groups
    graph = SimilarityGraph(threshold=0.95)

    # Create files with very different content
    file1 = TextFile.from_path(create_file_with_content("test1.txt", "hello world"))
    file2 = TextFile.from_path(create_file_with_content("test2.txt", "hello world"))
    file3 = TextFile.from_path(
        create_file_with_content(
            "test3.txt",
            "This is a completely different text with no similarity whatsoever",
        )
    )

    graph.add_files([file1, file2, file3])
    groups = graph.get_groups()

    # Verify we have groups
    assert len(groups) > 0

    # Find files that are grouped together
    similar_files = set()
    for group in groups:
        if len(group.files) > 1:
            similar_files.update(group.files)

    # Verify that file1 and file2 are grouped together
    assert file1.path in similar_files
    assert file2.path in similar_files
    # Verify that file3 is not grouped with the others
    assert file3.path not in similar_files


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
