"""Tests for exception handling edge cases."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess
import git_commitai


def test_auto_stage_called_process_error():
    """Test CalledProcessError in auto-stage flow (line 469)."""
    with patch("subprocess.run") as mock_run:
        # First call: git diff --quiet raises CalledProcessError (has unstaged changes)
        # Second call: git add -u raises CalledProcessError (staging fails)
        mock_run.side_effect = [
            MagicMock(returncode=1),  # git diff --quiet (changes exist)
            subprocess.CalledProcessError(1, 'git add -u'),  # staging fails
        ]

        # Should handle exception and return False
        result = git_commitai.check_staged_changes(auto_stage=True)

        assert result is False
        # Verify staging was attempted
        assert mock_run.call_count == 2


def test_check_staged_changes_called_process_error():
    """Test CalledProcessError handling in check_staged_changes (line 500-501)."""
    with patch("subprocess.run") as mock_run:
        # Simulate CalledProcessError in subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git diff')

        # Should handle exception and return False
        result = git_commitai.check_staged_changes()

        assert result is False


def test_binary_file_info_size_error():
    """Test exception handling in get_binary_file_info for size retrieval (line 645)."""
    with patch("git_commitai.run_git") as mock_run_git:
        # Simulate git cat-file -s failing
        mock_run_git.side_effect = Exception("File not found")

        # Should handle exception gracefully
        result = git_commitai.get_binary_file_info("missing.png")

        # Should still return info, just without size
        assert "File type: .png" in result or "PNG image" in result
        # Should not crash


def test_get_staged_files_file_processing_error():
    """Test exception when processing individual file (line 817-820)."""
    with patch("git_commitai.run_git") as mock_run_git:
        # File list succeeds, but processing individual file fails
        mock_run_git.side_effect = [
            "file1.txt\nfile2.txt",  # File list
            "",                       # numstat for file1
            Exception("Error reading file1"),  # Error on file1 content
            "",                       # numstat for file2
            "content2",               # file2 content (succeeds)
        ]

        result = git_commitai.get_staged_files()

        # file1 should be skipped due to error, file2 should work
        assert "file2.txt" in result
        assert "content2" in result
        # file1 should not cause crash


def test_git_root_fallback_on_exception():
    """Test get_git_root falls back to cwd on exception (line 138-139)."""
    with patch("git_commitai.run_git") as mock_run_git, \
         patch("os.getcwd", return_value="/fallback/path"):

        mock_run_git.side_effect = Exception("Not a git repo")

        result = git_commitai.get_git_root()

        assert result == "/fallback/path"


def test_load_gitcommitai_config_exception():
    """Test load_gitcommitai_config handles exceptions gracefully (line 208-209)."""
    with patch("git_commitai.get_git_root", return_value="/tmp"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=IOError("Permission denied")):

        # Should handle exception and return empty config
        result = git_commitai.load_gitcommitai_config()

        assert result == {}


def test_read_gitmessage_template_io_error():
    """Test read_gitmessage_template handles IO errors (line 972-973, etc)."""
    with patch("git_commitai.get_git_root", return_value="/tmp"), \
         patch("os.path.isfile", return_value=True), \
         patch("builtins.open", side_effect=IOError("Read error")):

        # Should handle error and return None
        result = git_commitai.read_gitmessage_template()

        assert result is None


def test_get_current_branch_exception():
    """Test get_current_branch handles exceptions (line 938-939)."""
    with patch("git_commitai.run_git", side_effect=Exception("Git error")):

        result = git_commitai.get_current_branch()

        assert result == "unknown"


def test_is_commit_message_empty_io_error():
    """Test is_commit_message_empty handles IO errors (line 1436-1439)."""
    with patch("builtins.open", side_effect=IOError("Cannot read file")):

        # Should handle error and return True (treat as empty)
        result = git_commitai.is_commit_message_empty("/nonexistent/file")

        assert result is True


def test_show_git_status_exception():
    """Test show_git_status handles exceptions (line 598-601)."""
    with patch("git_commitai.run_git", side_effect=Exception("Git error")), \
         patch("builtins.print") as mock_print:

        # Should not crash, should show fallback message
        git_commitai.show_git_status()

        # Verify fallback message was printed
        printed_lines = [str(call[0][0]) for call in mock_print.call_args_list]
        assert any("No changes staged" in line or "branch" in line for line in printed_lines)


def test_open_editor_exception():
    """Test open_editor handles subprocess exceptions."""
    with patch("subprocess.run", side_effect=Exception("Editor not found")), \
         patch("builtins.print") as mock_print:

        with pytest.raises(SystemExit) as exc_info:
            git_commitai.open_editor("/tmp/file", "invalid_editor")

        assert exc_info.value.code == 1
        # Verify error message was printed
        mock_print.assert_called()


def test_strip_comments_and_save_io_error():
    """Test strip_comments_and_save handles IO errors."""
    with patch("builtins.open", side_effect=IOError("Write error")), \
         patch("builtins.print") as mock_print:

        result = git_commitai.strip_comments_and_save("/tmp/file")

        assert result is False
        # Verify error was printed
        mock_print.assert_called()


def test_auto_stage_success_path():
    """Test successful auto-staging (lines 461-468)."""
    with patch("subprocess.run") as mock_run:
        # git diff --quiet returns 1 (has changes)
        # git add -u succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1),  # diff --quiet: changes exist
            MagicMock(returncode=0),  # add -u: success
            MagicMock(returncode=1, stdout=""),  # diff --cached --quiet: has staged changes
        ]

        result = git_commitai.check_staged_changes(auto_stage=True)

        assert result is True
        assert mock_run.call_count == 3


def test_auto_stage_no_unstaged_changes():
    """Test auto-stage when no unstaged changes exist (line 467)."""
    with patch("subprocess.run") as mock_run:
        # git diff --quiet returns 0 (no changes)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # diff --quiet: no unstaged changes
            MagicMock(returncode=1, stdout=""),  # diff --cached --quiet: has staged changes
        ]

        result = git_commitai.check_staged_changes(auto_stage=True)

        assert result is True
        # git add -u should NOT be called
        assert mock_run.call_count == 2
