"""Tests for total size limits (MAX_TOTAL_FILES, MAX_DIFF_SIZE)."""

import pytest
from unittest.mock import patch
import git_commitai


def test_total_files_size_limit():
    """Test that total files size is enforced."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("git_commitai.MAX_FILE_SIZE", 10 * 1024), \
         patch("git_commitai.MAX_TOTAL_FILES", 15 * 1024):  # 15KB total limit

        # Three files: 8KB, 8KB, 8KB = 24KB total (exceeds 15KB limit)
        file1_content = "x" * (8 * 1024)
        file2_content = "y" * (8 * 1024)
        file3_content = "z" * (8 * 1024)

        mock_run_git.side_effect = [
            "file1.txt\nfile2.txt\nfile3.txt",  # file list
            "",  # numstat file1
            file1_content,  # content file1 (8KB, fits)
            "",  # numstat file2
            file2_content,  # content file2 (8KB, total now 16KB > 15KB limit)
            "",  # numstat file3
            file3_content,  # content file3 (won't be added)
        ]

        result = git_commitai.get_staged_files()

        # First file should be included (8KB < 15KB)
        assert "file1.txt" in result
        assert file1_content in result

        # Second file would exceed limit (8KB + 8KB = 16KB > 15KB)
        assert "file2.txt" in result
        assert "size limit" in result
        assert file2_content not in result

        # Third file also excluded
        assert "file3.txt" in result
        assert file3_content not in result


def test_diff_size_truncation():
    """Test that large diffs are truncated."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("git_commitai.MAX_DIFF_SIZE", 1024):  # 1KB limit

        # Create a diff larger than 1KB
        large_diff = "\n".join([f"+ line {i}" for i in range(100)])  # ~700 bytes
        large_diff += "\n" + "\n".join([f"- old line {i}" for i in range(100)])  # ~1400 bytes total

        mock_run_git.return_value = large_diff

        result = git_commitai.get_git_diff()

        # Should contain truncation marker
        assert "TRUNCATED" in result
        assert "diff too large" in result or "lines omitted" in result
        # Should show original size
        assert "1." in result or "KB" in result
        # Full diff should not be in result
        assert len(result) < len(large_diff)


def test_diff_under_size_limit():
    """Test that small diffs are not truncated."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("git_commitai.MAX_DIFF_SIZE", 10 * 1024):  # 10KB limit

        small_diff = "\n".join([f"+ line {i}" for i in range(10)])  # ~100 bytes

        mock_run_git.return_value = small_diff

        result = git_commitai.get_git_diff()

        # Should NOT contain truncation marker
        assert "TRUNCATED" not in result
        # Should contain full diff
        assert small_diff in result


def test_gitcommitai_config_size_overrides():
    """Test that .gitcommitai config can override size limits."""
    config_content = """model: gpt-4
max_file_size: 50000
max_total_files: 200000
max_diff_size: 100000
max_prompt_size: 500000

You are a commit message generator.
"""

    with patch("git_commitai.get_git_root", return_value="/test"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", create=True) as mock_open:

        mock_open.return_value.__enter__.return_value.read.return_value = config_content

        config = git_commitai.load_gitcommitai_config()

        assert config['model'] == 'gpt-4'
        assert config['max_file_size'] == 50000
        assert config['max_total_files'] == 200000
        assert config['max_diff_size'] == 100000
        assert config['max_prompt_size'] == 500000


def test_total_files_respects_per_file_limit():
    """Test that per-file limit is checked before total limit."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("git_commitai.MAX_FILE_SIZE", 5 * 1024), \
         patch("git_commitai.MAX_TOTAL_FILES", 20 * 1024):

        # One file that exceeds per-file limit
        huge_file = "x" * (10 * 1024)  # 10KB

        mock_run_git.side_effect = [
            "huge.txt",
            "",
            huge_file,
        ]

        result = git_commitai.get_staged_files()

        # Should be rejected due to per-file limit, not total limit
        assert "huge.txt" in result
        assert "too large" in result
        assert "5.0KB" in result  # Shows per-file limit
        assert huge_file not in result


def test_empty_files_dont_count_toward_total():
    """Test that empty files are included and don't affect total size."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("git_commitai.MAX_FILE_SIZE", 10 * 1024), \
         patch("git_commitai.MAX_TOTAL_FILES", 5 * 1024):

        mock_run_git.side_effect = [
            "empty.txt\nsmall.txt",
            "",  # numstat empty
            "",  # content empty (0 bytes)
            "",  # numstat small
            "hello",  # content small (5 bytes)
        ]

        result = git_commitai.get_staged_files()

        # Both files should be included
        assert "empty.txt" in result
        assert "small.txt" in result
        assert "hello" in result
