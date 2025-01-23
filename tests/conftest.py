"""Common test fixtures."""

import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional

import pytest
from rich.console import Console

from ndetect.models import (
    MoveConfig,
    PreviewConfig,
    RetentionConfig,
    TextFile,
)
from ndetect.similarity import SimilarityGraph
from ndetect.ui import InteractiveUI


@pytest.fixture
def duplicates_dir(tmp_path: Path) -> Path:
    """Create and return a temporary duplicates directory."""
    dup_dir = tmp_path / "duplicates"
    dup_dir.mkdir()
    return dup_dir


@pytest.fixture
def cleanup_duplicates() -> Generator[None, None, None]:
    """Fixture to clean up the duplicates directory after tests."""
    yield
    if Path("duplicates").exists():
        shutil.rmtree("duplicates")


@pytest.fixture
def test_console() -> Console:
    """Create a test console with consistent settings."""
    return Console(force_terminal=True, no_color=True, width=100)


@pytest.fixture
def test_console_no_color() -> Console:
    """Create a test console with no color for consistent output testing."""
    return Console(force_terminal=True, no_color=True, width=100)


@pytest.fixture
def configurable_ui(
    test_console: Console,
    duplicates_dir: Path,
    retention_strategy: str = "newest",
    preview_max_chars: int = 20,
    preview_max_lines: int = 2,
) -> InteractiveUI:
    """Create a configurable InteractiveUI instance."""
    return InteractiveUI(
        console=test_console,
        move_config=MoveConfig(holding_dir=duplicates_dir),
        retention_config=RetentionConfig(strategy=retention_strategy),
        preview_config=PreviewConfig(
            max_chars=preview_max_chars, max_lines=preview_max_lines
        ),
    )


@pytest.fixture
def create_test_files(tmp_path: Path) -> Generator[List[Path], None, None]:
    """Create test files with specified content and timestamps."""
    files: List[Path] = []

    def _create_file(name: str, content: str, mtime: Optional[float] = None) -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        if mtime is not None:
            os.utime(file_path, (mtime, mtime))
        files.append(file_path)
        return file_path

    yield [
        _create_file("test1.txt", "content1", time.time() - 100),
        _create_file("test2.txt", "content2", time.time()),
        _create_file("test3.txt", "content3", time.time() + 100),
    ]

    # Cleanup
    for file in files:
        if file.exists():
            file.unlink()


@pytest.fixture
def similarity_graph(threshold: float = 0.8) -> SimilarityGraph:
    """Create a SimilarityGraph with default settings."""
    return SimilarityGraph(threshold=threshold)


@pytest.fixture
def create_file_with_content(tmp_path: Path) -> Callable[[str, str], Path]:
    """Create a file with given content."""

    def _create(name: str, content: str) -> Path:
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path

    return _create


@pytest.fixture
def create_text_file(tmp_path: Path) -> Callable[[str, str], TextFile]:
    """Factory fixture to create TextFile instances."""

    def _create(name: str, content: str) -> TextFile:
        file_path = tmp_path / name
        file_path.write_text(content)
        return TextFile.from_path(file_path)

    return _create


@pytest.fixture
def mock_prompt_responses() -> Callable[[dict[str, Any]], Callable[..., Any]]:
    """Create a mock prompt handler with predefined responses."""

    def _create_mock(responses: dict[str, Any]) -> Callable[..., Any]:
        def mock_confirm(*args: Any, **kwargs: Any) -> Any:
            msg = str(args[0] if args else kwargs.get("prompt", ""))
            for key, response in responses.items():
                if key in msg:
                    return response
            return True  # Default response

        return mock_confirm

    return _create_mock
