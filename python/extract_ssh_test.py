"""Tests for extract_ssh.py."""

import io
import subprocess
import sys
import typing
import unittest
from unittest import mock

import extract_ssh


class TestExtractSsh(unittest.TestCase):
    """Tests for the extract_ssh module."""

    def test_extract_ssh_details_success(self) -> None:
        """Tests extract_ssh_details when the ssh command succeeds."""
        mock_process = typing.cast(
            subprocess.CompletedProcess[str],
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_process.stdout = "\nhost example.com\nport 22\nuser testuser\nsome_key\n"

        with mock.patch.object(
            subprocess, "run", return_value=mock_process
        ) as mock_run:
            details = extract_ssh.extract_ssh_details(
                ssh_args=["ssh", "testuser@example.com"]
            )
            self.assertEqual(details.hostname, "example.com")
            self.assertEqual(details.username, "testuser")
            mock_run.assert_called_once_with(
                ["ssh", "-G", "testuser@example.com"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_extract_ssh_details_missing_hostname(self) -> None:
        """Tests that extract_ssh_details raises ValueError if hostname is missing."""
        mock_process = typing.cast(
            subprocess.CompletedProcess[str],
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_process.stdout = "user testuser\n"

        with mock.patch.object(subprocess, "run", return_value=mock_process):
            with self.assertRaises(KeyError):
                extract_ssh.extract_ssh_details(
                    ssh_args=["ssh", "testuser@example.com"]
                )

    def test_extract_ssh_details_missing_user(self) -> None:
        """Tests that extract_ssh_details raises ValueError if user is missing."""
        mock_process = typing.cast(
            subprocess.CompletedProcess[str],
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_process.stdout = "hostname example.com\n"

        with mock.patch.object(subprocess, "run", return_value=mock_process):
            with self.assertRaises(KeyError):
                extract_ssh.extract_ssh_details(ssh_args=["ssh", "example.com"])

    def test_main_success(self) -> None:
        """Tests that main prints username@host and exits normally."""
        details = extract_ssh.SshDetails(hostname="example.com", username="testuser")
        with (
            mock.patch.object(
                extract_ssh, "extract_ssh_details", return_value=details
            ) as mock_extract,
            mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout,
        ):
            extract_ssh.main(argv=["extract_ssh.py", "ssh", "testuser@example.com"])
            mock_extract.assert_called_once_with(
                ssh_args=["ssh", "testuser@example.com"]
            )
            self.assertEqual(
                mock_stdout.getvalue(),
                "testuser@example.com\n",
            )


if __name__ == "__main__":
    unittest.main()
