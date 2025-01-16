"""Common test fixtures."""

import shutil
from pathlib import Path
from typing import Generator

import pytest


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
