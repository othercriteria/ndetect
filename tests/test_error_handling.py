import shutil
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch

import pytest

from ndetect.exceptions import DiskSpaceError, FileOperationError, PermissionError
from ndetect.operations import MoveOperation, execute_moves, rollback_moves
from ndetect.utils import check_disk_space, get_total_size


def test_disk_space_check(tmp_path: Path) -> None:
    """Test disk space checking functionality."""
    file = tmp_path / "test.txt"
    file.write_text("test content")

    # Mock disk_usage to return known values
    mock_usage = Mock(free=1000)
    with patch("shutil.disk_usage", return_value=mock_usage):
        # Should pass when requiring less space
        check_disk_space(file, 500)

        # Should raise when requiring more space
        with pytest.raises(DiskSpaceError) as exc_info:
            check_disk_space(file, 2000)

        assert exc_info.value.required_bytes == 2000
        assert exc_info.value.available_bytes == 1000


def test_get_total_size(tmp_path: Path) -> None:
    """Test total size calculation."""
    files: List[Path] = []
    sizes = [100, 200, 300]

    for i, size in enumerate(sizes):
        file = tmp_path / f"test{i}.txt"
        file.write_text("x" * size)
        files.append(file)

    total = get_total_size(files)
    assert total == sum(sizes)


def test_execute_moves_rollback(tmp_path: Path) -> None:
    """Test rollback functionality when moves fail."""
    # Create test directory structure
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    # Create test files
    files: List[Path] = []
    for i in range(3):
        file = source_dir / f"test{i}.txt"
        file.write_text(f"content {i}")
        files.append(file)

    # Create move operations
    moves = [
        MoveOperation(source=file, destination=dest_dir / file.name, group_id=1)
        for file in files
    ]

    # Mock shutil.move to fail on the second file
    original_move = shutil.move
    move_called = 0

    def mock_move(src: str, dst: str) -> None:
        nonlocal move_called
        move_called += 1
        if move_called == 2:
            # Use our custom PermissionError
            raise PermissionError(str(src), "move")
        original_move(src, dst)

    with patch("shutil.move", side_effect=mock_move):
        with pytest.raises(PermissionError):
            execute_moves(moves)

        # Verify first file was moved and then rolled back
        assert files[0].exists()
        assert not (dest_dir / files[0].name).exists()
        # Verify other files weren't moved
        assert files[1].exists()
        assert files[2].exists()


def test_execute_moves_insufficient_space(tmp_path: Path) -> None:
    """Test handling of insufficient disk space."""
    source_file = tmp_path / "source.txt"
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    source_file.write_text("test content")
    move = MoveOperation(
        source=source_file, destination=dest_dir / "source.txt", group_id=1
    )

    # Mock disk_usage to simulate insufficient space
    mock_usage = Mock(free=10)  # Only 10 bytes free
    with patch("shutil.disk_usage", return_value=mock_usage):
        with pytest.raises(DiskSpaceError):
            execute_moves([move])

        # Verify file wasn't moved
        assert source_file.exists()
        assert not (dest_dir / "source.txt").exists()


def test_rollback_moves_error_handling(tmp_path: Path) -> None:
    """Test handling of errors during rollback."""
    # Create test files and perform initial moves
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    moves: List[MoveOperation] = []
    for i in range(2):
        src = source_dir / f"test{i}.txt"
        dst = dest_dir / f"test{i}.txt"
        src.write_text(f"content {i}")
        shutil.move(str(src), str(dst))
        moves.append(MoveOperation(source=src, destination=dst, group_id=1))

    # Mock shutil.move to fail during rollback
    def mock_move_error(src: str, dst: str) -> None:
        raise OSError("Rollback failed")  # Use OSError instead of FileOperationError

    with patch("shutil.move", side_effect=mock_move_error):
        # Rollback should continue despite errors
        rollback_moves(moves)

        # Check that original files still exist in destination
        assert (dest_dir / "test0.txt").exists()
        assert (dest_dir / "test1.txt").exists()


def test_error_message_formatting(tmp_path: Path) -> None:
    """Test error message formatting in non-interactive mode."""
    file = tmp_path / "test.txt"
    file.write_text("test content")

    # Test disk space error
    with patch("shutil.disk_usage", return_value=Mock(free=100)):
        with pytest.raises(DiskSpaceError) as exc_info:
            check_disk_space(file, 1000)

        error = exc_info.value
        assert "Need 1,000 bytes" in str(error)
        assert "100 available" in str(error)

    # Test permission error
    perm_error = PermissionError(str(file), "read")
    assert "Permission denied" in str(perm_error)
    assert str(file) in str(perm_error)
    assert "read" in str(perm_error)


def test_execute_moves_total_disk_space(
    create_test_files: List[Path], duplicates_dir: Path
) -> None:
    """Test total disk space checking across all destinations."""
    files = create_test_files
    total_size = sum(f.stat().st_size for f in files)

    moves = [
        MoveOperation(
            source=files[0],
            destination=duplicates_dir / "test1.txt",
            group_id=1,
        ),
        MoveOperation(
            source=files[1],
            destination=duplicates_dir / "test2.txt",
            group_id=1,
        ),
        MoveOperation(
            source=files[2],
            destination=duplicates_dir / "test3.txt",
            group_id=1,
        ),
    ]

    with patch("shutil.disk_usage") as mock_disk_usage:
        # Mock disk space to be half of what's needed
        mock_disk_usage.return_value = Mock(free=total_size // 2)

        with pytest.raises(DiskSpaceError) as exc_info:
            execute_moves(moves)

        assert exc_info.value.required_bytes > exc_info.value.available_bytes
        assert all(f.exists() for f in files)  # Verify no files were moved


def test_execute_moves_disk_space(
    create_test_files: List[Path], duplicates_dir: Path
) -> None:
    """Test disk space checking for moves."""
    files = create_test_files[:3]  # Get first three test files
    total_size = sum(f.stat().st_size for f in files)

    moves = [
        MoveOperation(
            source=files[0],
            destination=duplicates_dir / "test1.txt",
            group_id=1,
        ),
        MoveOperation(
            source=files[1],
            destination=duplicates_dir / "test2.txt",
            group_id=1,
        ),
        MoveOperation(
            source=files[2],
            destination=duplicates_dir / "test3.txt",
            group_id=1,
        ),
    ]

    with patch("shutil.disk_usage") as mock_disk_usage:
        # Mock disk space that's less than total needed
        mock_disk_usage.return_value = Mock(free=total_size // 2)

        with pytest.raises(DiskSpaceError) as exc_info:
            execute_moves(moves)

        # Verify the error is about total space
        assert exc_info.value.required_bytes > exc_info.value.available_bytes

        # Verify no files were moved
        assert all(f.exists() for f in files)
        assert not any((duplicates_dir / f"test{i}.txt").exists() for i in range(1, 4))


def test_execute_moves_successful(tmp_path: Path) -> None:
    """Test successful execution of moves with sufficient disk space."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"

    file1.write_text("x" * 1000)  # 1000 bytes
    file2.write_text("x" * 2000)  # 2000 bytes

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    moves = [
        MoveOperation(source=file1, destination=dest_dir / "test1.txt", group_id=1),
        MoveOperation(source=file2, destination=dest_dir / "test2.txt", group_id=1),
    ]

    # Test with sufficient space
    with patch("shutil.disk_usage") as mock_disk_usage:
        mock_disk_usage.return_value = Mock(free=10000)  # More than enough space
        execute_moves(moves)

        # Verify files were moved correctly
        assert not file1.exists()
        assert not file2.exists()
        assert (dest_dir / "test1.txt").exists()
        assert (dest_dir / "test2.txt").exists()

        # Verify content was preserved
        assert (dest_dir / "test1.txt").read_text() == "x" * 1000
        assert (dest_dir / "test2.txt").read_text() == "x" * 2000


def test_execute_moves_empty_list(tmp_path: Path) -> None:
    """Test handling of empty moves list."""
    with patch("shutil.disk_usage") as mock_disk_usage:
        execute_moves([])  # Should return without error
        mock_disk_usage.assert_not_called()  # Should not check disk space


def test_execute_moves_disk_space_error_types(tmp_path: Path) -> None:
    """Test different types of disk space errors."""
    file1 = tmp_path / "test1.txt"
    file1.write_text("x" * 1000)

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    moves = [
        MoveOperation(source=file1, destination=dest_dir / "test1.txt", group_id=1),
    ]

    # Test OSError during disk space check
    with patch("shutil.disk_usage", side_effect=OSError("Mock disk error")):
        with pytest.raises(FileOperationError) as exc_info:
            execute_moves(moves)
        assert "check space" in str(exc_info.value)
        assert "Mock disk error" in str(exc_info.value)
        assert file1.exists()  # File should not be moved


def test_execute_moves_zero_byte_files(tmp_path: Path) -> None:
    """Test handling of zero-byte files."""
    # Create empty files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"

    file1.touch()
    file2.touch()

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    moves = [
        MoveOperation(source=file1, destination=dest_dir / "test1.txt", group_id=1),
        MoveOperation(source=file2, destination=dest_dir / "test2.txt", group_id=1),
    ]

    # Even with no free space, zero-byte files should move
    with patch("shutil.disk_usage") as mock_disk_usage:
        mock_disk_usage.return_value = Mock(free=0)
        execute_moves(moves)

        # Verify files were moved
        assert not file1.exists()
        assert not file2.exists()
        assert (dest_dir / "test1.txt").exists()
        assert (dest_dir / "test2.txt").exists()
