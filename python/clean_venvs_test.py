"""Tests for clean_venvs.py."""

import io
import os
import pathlib
import sys
import unittest
from unittest import mock
import typing

from pyfakefs import fake_filesystem_unittest

import clean_venvs


class TestArgs(unittest.TestCase):
    """Tests for the Args class."""

    def test_init_defaults(self) -> None:
        """Tests that Args initializes with correct defaults."""
        args = clean_venvs.Args()
        self.assertEqual(args.directory, "~/tmp/bin/virtualenv/")
        self.assertFalse(args.dry_run)
        self.assertFalse(args.verbose)
        self.assertEqual(args.symlink_name, "Python")

    def test_init_custom(self) -> None:
        """Tests that Args initializes with provided values."""
        args = clean_venvs.Args(
            directory="/custom/path",
            dry_run=True,
            verbose=True,
            symlink_name="python",
        )
        self.assertEqual(args.directory, "/custom/path")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.verbose)
        self.assertEqual(args.symlink_name, "python")


class TestCleanVirtualenvs(fake_filesystem_unittest.TestCase):
    """Tests for the clean_virtualenvs function."""

    @typing.override
    def setUp(self) -> None:
        """Set up fake filesystem."""
        self.setUpPyfakefs()

    def test_clean_virtualenvs_basic(self) -> None:
        """Tests standard venv cleanup keeping the active one."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv)
        os.makedirs(inactive_venv)

        # Create symlink pointing to active
        os.symlink("2026-06-26", virtualenv_dir / "Python")

        # Create a regular file in the directory
        with open(virtualenv_dir / "regular_file.txt", "w") as f:
            f.write("hello")

        self.assertTrue(active_venv.is_dir())
        self.assertTrue(inactive_venv.is_dir())
        self.assertTrue((virtualenv_dir / "regular_file.txt").is_file())

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=False,
            verbose=False,
        )

        self.assertTrue(active_venv.is_dir())
        self.assertFalse(inactive_venv.is_dir())
        self.assertTrue((virtualenv_dir / "Python").is_symlink())
        self.assertTrue((virtualenv_dir / "regular_file.txt").is_file())

    def test_clean_virtualenvs_lowercase_fallback(self) -> None:
        """Tests fallback to lowercase python symlink if Python is absent."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv)
        os.makedirs(inactive_venv)

        # Create lowercase python symlink pointing to active
        os.symlink("2026-06-26", virtualenv_dir / "python")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=False,
            verbose=False,
        )

        self.assertTrue(active_venv.is_dir())
        self.assertFalse(inactive_venv.is_dir())
        self.assertTrue((virtualenv_dir / "python").is_symlink())

    def test_clean_virtualenvs_nested_active(self) -> None:
        """Tests keeping directories when symlink points to a nested path."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv_dir = virtualenv_dir / "2026-06-26"
        active_venv_subdir = active_venv_dir / "venv"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv_subdir)
        os.makedirs(inactive_venv)

        os.symlink("2026-06-26/venv", virtualenv_dir / "Python")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=False,
            verbose=False,
        )

        self.assertTrue(active_venv_dir.is_dir())
        self.assertTrue(active_venv_subdir.is_dir())
        self.assertFalse(inactive_venv.is_dir())

    def test_clean_virtualenvs_dry_run(self) -> None:
        """Tests dry run does not delete anything."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv)
        os.makedirs(inactive_venv)

        os.symlink("2026-06-26", virtualenv_dir / "Python")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=True,
            verbose=False,
        )

        self.assertTrue(active_venv.is_dir())
        self.assertTrue(inactive_venv.is_dir())

    def test_clean_virtualenvs_missing_directory(self) -> None:
        """Tests FileNotFoundError when target directory is missing."""
        virtualenv_dir = pathlib.Path("/nonexistent")

        with self.assertRaisesRegex(FileNotFoundError, "Directory not found"):
            clean_venvs.clean_virtualenvs(
                virtualenv_dir=virtualenv_dir,
                symlink_name="Python",
                dry_run=False,
                verbose=False,
            )

    def test_clean_virtualenvs_missing_symlink(self) -> None:
        """Tests FileNotFoundError when active symlink is missing."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        os.makedirs(virtualenv_dir)

        with self.assertRaisesRegex(FileNotFoundError, "Active venv symlink not found"):
            clean_venvs.clean_virtualenvs(
                virtualenv_dir=virtualenv_dir,
                symlink_name="Python",
                dry_run=False,
                verbose=False,
            )

    def test_clean_virtualenvs_broken_symlink(self) -> None:
        """Tests FileNotFoundError when active symlink is broken."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        os.makedirs(virtualenv_dir)
        os.symlink("nonexistent_target", virtualenv_dir / "Python")

        with self.assertRaisesRegex(FileNotFoundError, "points to a non-existent path"):
            clean_venvs.clean_virtualenvs(
                virtualenv_dir=virtualenv_dir,
                symlink_name="Python",
                dry_run=False,
                verbose=False,
            )

    def test_clean_virtualenvs_extra_symlink_deleted(self) -> None:
        """Tests that other symlinks in the directory are deleted."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        os.makedirs(active_venv)
        os.symlink("2026-06-26", virtualenv_dir / "Python")

        # Create another symlink pointing elsewhere
        os.symlink("2026-06-26", virtualenv_dir / "OtherSymlink")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=False,
            verbose=False,
        )

        self.assertFalse((virtualenv_dir / "OtherSymlink").exists())
        self.assertFalse((virtualenv_dir / "OtherSymlink").is_symlink())
        self.assertTrue((virtualenv_dir / "Python").is_symlink())

    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_clean_virtualenvs_verbose(self, mock_stdout: io.StringIO) -> None:
        """Tests verbose output logging."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv)
        os.makedirs(inactive_venv)
        os.symlink("2026-06-26", virtualenv_dir / "Python")
        # Also add an inactive symlink to test verbose symlink deletion
        os.symlink("2026-06-26", virtualenv_dir / "inactive_symlink")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=False,
            verbose=True,
        )

        output = mock_stdout.getvalue()
        self.assertIn("Active venv resolved to:", output)
        self.assertIn("Keeping active venv directory:", output)
        self.assertIn("Deleting directory:", output)
        self.assertIn("Deleting symlink:", output)

    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_clean_virtualenvs_dry_run_symlink(self, mock_stdout: io.StringIO) -> None:
        """Tests dry run with an inactive symlink."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        os.makedirs(active_venv)
        os.symlink("2026-06-26", virtualenv_dir / "Python")
        os.symlink("2026-06-26", virtualenv_dir / "inactive_symlink")

        clean_venvs.clean_virtualenvs(
            virtualenv_dir=virtualenv_dir,
            symlink_name="Python",
            dry_run=True,
            verbose=False,
        )

        self.assertTrue((virtualenv_dir / "inactive_symlink").is_symlink())
        output = mock_stdout.getvalue()
        self.assertIn("[DRY RUN] Would delete symlink:", output)

    def test_clean_virtualenvs_resolve_failure(self) -> None:
        """Tests that a directory failing to resolve is safely skipped."""
        virtualenv_dir = pathlib.Path("/fake/virtualenv")
        active_venv = virtualenv_dir / "2026-06-26"
        inactive_venv = virtualenv_dir / "2026-06-25"

        os.makedirs(active_venv)
        os.makedirs(inactive_venv)
        os.symlink("2026-06-26", virtualenv_dir / "Python")

        original_resolve = pathlib.Path.resolve

        def resolve_side_effect(
            self_obj: pathlib.Path, strict: bool = False
        ) -> pathlib.Path:
            if self_obj.name == "2026-06-25":
                raise FileNotFoundError("mock error")
            return original_resolve(self_obj, strict=strict)

        with mock.patch.object(
            pathlib.Path, "resolve", autospec=True, side_effect=resolve_side_effect
        ):
            clean_venvs.clean_virtualenvs(
                virtualenv_dir=virtualenv_dir,
                symlink_name="Python",
                dry_run=False,
                verbose=False,
            )

        # The inactive_venv shouldn't have been deleted because resolve failed and it skipped
        self.assertTrue(inactive_venv.is_dir())


class TestMain(unittest.TestCase):
    """Tests for the main function."""

    @mock.patch.object(clean_venvs, "clean_virtualenvs")
    def test_main_success(self, mock_clean: mock.Mock) -> None:
        """Tests main with default arguments (successful path)."""
        ret_val = clean_venvs.main(["clean_venvs.py"])
        self.assertEqual(ret_val, 0)
        mock_clean.assert_called_once_with(
            virtualenv_dir=pathlib.Path("~/tmp/bin/virtualenv/").expanduser(),
            symlink_name="Python",
            dry_run=False,
            verbose=False,
        )

    @mock.patch.object(clean_venvs, "clean_virtualenvs")
    def test_main_custom_args(self, mock_clean: mock.Mock) -> None:
        """Tests main with custom arguments."""
        ret_val = clean_venvs.main(
            [
                "clean_venvs.py",
                "/custom/dir",
                "-n",
                "-v",
                "--symlink-name",
                "python",
            ]
        )
        self.assertEqual(ret_val, 0)
        mock_clean.assert_called_once_with(
            virtualenv_dir=pathlib.Path("/custom/dir"),
            symlink_name="python",
            dry_run=True,
            verbose=True,
        )

    @mock.patch.object(
        clean_venvs,
        "clean_virtualenvs",
        side_effect=FileNotFoundError("Mock error message"),
    )
    @mock.patch.object(sys, "stderr", new_callable=io.StringIO)
    def test_main_failure(
        self, mock_stderr: io.StringIO, _mock_clean: mock.Mock
    ) -> None:
        """Tests main handling of FileNotFoundError."""
        ret_val = clean_venvs.main(["clean_venvs.py"])
        self.assertEqual(ret_val, 1)
        self.assertIn("Error: Mock error message", mock_stderr.getvalue())
