"""Tests for get_git_root.py."""

import subprocess
from typing import cast
import unittest
from unittest import mock

import get_git_root


class TestGetGitRoot(unittest.TestCase):
    """Tests for the get_git_root function."""

    def test_get_git_root_success(self) -> None:
        """Tests get_git_root when git command succeeds."""
        mock_completed_process = cast(
            subprocess.CompletedProcess[str],
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_completed_process.stdout = "/repo/root\n"
        with mock.patch.object(
            subprocess, "run", return_value=mock_completed_process
        ) as mock_run:
            root = get_git_root.get_git_root()
            self.assertEqual(root, "/repo/root")
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_get_git_root_failure(self) -> None:
        """Tests that get_git_root raises an error when git command fails."""
        with mock.patch.object(
            subprocess, "run", side_effect=subprocess.CalledProcessError(1, "git")
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                get_git_root.get_git_root()


if __name__ == "__main__":
    unittest.main()
