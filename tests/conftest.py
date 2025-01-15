"""Common test fixtures."""

import shutil
from pathlib import Path
import pytest
from typing import Generator
@pytest.fixture
def cleanup_duplicates() -> Generator[None, None, None]:
    """Clean up duplicates directory after test."""
    yield
    duplicates_dir = Path("duplicates")
    if duplicates_dir.exists():
        shutil.rmtree(duplicates_dir) 