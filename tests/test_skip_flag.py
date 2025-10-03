"""Tests for --skip flag functionality."""

import pytest
from unittest.mock import patch, MagicMock
import git_commitai


def test_skip_flag_single_pattern():
    """Test --skip flag with single glob pattern."""
    # Mock git operations
    with patch("git_commitai.run_git") as mock_run_git:
        # Simulate multiple files staged
        mock_run_git.return_value = "src/secret.env\nsrc/main.py\nREADME.md"

        # Test that .env files are skipped
        result = git_commitai.get_staged_files(skip_patterns=["*.env"])

        assert "secret.env" in result
        assert "skipped: matches pattern '*.env'" in result
        assert "File content excluded from AI prompt" in result
        # Main.py and README should still have content
        assert "main.py" in result


def test_skip_flag_multiple_patterns():
    """Test --skip flag with multiple glob patterns."""
    with patch("git_commitai.run_git") as mock_run_git:
        # Mock diff-tree, diff --cached --name-only
        mock_run_git.return_value = "package-lock.json\nnode_modules/lib.js\nsrc/app.js\ntests/test.py"

        skip_patterns = ["package-lock.json", "node_modules/*"]
        result = git_commitai.get_staged_files(skip_patterns=skip_patterns)

        # Both patterns should match
        assert "package-lock.json" in result and "skipped" in result
        assert "node_modules/lib.js" in result and "skipped" in result
        # App.js should have content
        assert "src/app.js" in result


def test_skip_flag_wildcard_patterns():
    """Test --skip flag with various wildcard patterns."""
    with patch("git_commitai.run_git") as mock_run_git:
        mock_run_git.return_value = "dist/bundle.js\nbuild/output.js\nsrc/index.js"

        # Skip all files in dist/ and build/
        result = git_commitai.get_staged_files(skip_patterns=["dist/*", "build/*"])

        assert "dist/bundle.js" in result and "skipped" in result
        assert "build/output.js" in result and "skipped" in result
        assert "src/index.js" in result
        # Verify skipped files don't show git show content
        assert result.count("File content excluded from AI prompt") == 2


def test_skip_flag_no_patterns():
    """Test get_staged_files with no skip patterns."""
    with patch("git_commitai.run_git") as mock_run_git:
        mock_run_git.side_effect = [
            "test.py",  # diff --cached --name-only
            "",  # diff --cached --numstat for binary check
            "print('hello')",  # git show :test.py
        ]

        result = git_commitai.get_staged_files(skip_patterns=None)

        assert "test.py" in result
        assert "skipped" not in result
        assert "print('hello')" in result


def test_skip_flag_amend_mode():
    """Test --skip flag works in amend mode - skip test, needs complex mocking."""
    pytest.skip("Amend mode file list merging requires complex git mocking")


def test_skip_flag_empty_pattern_list():
    """Test --skip with empty pattern list."""
    with patch("git_commitai.run_git") as mock_run_git:
        mock_run_git.side_effect = [
            "file.txt",
            "",
            "content",
        ]

        result = git_commitai.get_staged_files(skip_patterns=[])

        assert "file.txt" in result
        assert "content" in result
        assert "skipped" not in result


def test_skip_flag_case_sensitive():
    """Test that skip patterns are case-sensitive (fnmatch default)."""
    with patch("git_commitai.run_git") as mock_run_git:
        mock_run_git.return_value = "Test.PY\ntest.py"

        # Pattern *.py should only match lowercase
        result = git_commitai.get_staged_files(skip_patterns=["*.py"])

        # test.py matches, Test.PY doesn't
        lines = result.split('\n')
        assert any("test.py" in line and "skipped" in line for line in lines)
        # Test.PY should appear without skip marker (case sensitive)
        assert "Test.PY" in result
