"""Tests for linkdirs."""

import io
import os
import re
import stat
import sys
import textwrap
from typing import override
import unittest
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import linkdirs


class TestMain(unittest.TestCase):
    """Tests for main()."""

    @mock.patch.object(linkdirs, "real_main", return_value=[])
    @mock.patch.object(sys, "exit")
    def test_success(self, mock_sys_exit: mock.Mock, _unused_mock_real_main: mock.Mock):
        """Successful run."""
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as mock_stderr:
            linkdirs.main(argv=[])
            warnings = mock_stderr.getvalue()
            self.assertEqual("", warnings)
        mock_sys_exit.assert_called_once_with(0)

    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    @mock.patch.object(linkdirs, "real_main", return_value=["a message"])
    @mock.patch.object(sys, "exit")
    def test_failure(
        self,
        mock_sys_exit: mock.Mock,
        _unused_mock_real_main: mock.Mock,
        mock_stdout: io.StringIO,
    ):
        """Failed run."""
        linkdirs.main(argv=[])
        self.assertEqual("a message\n", mock_stdout.getvalue())
        # In reality sys.exit will only be called once, but because we mock it out
        # the flow control continues and it is called twice.
        mock_sys_exit.assert_has_calls([mock.call(1), mock.call(0)])


class TestIntegration(fake_filesystem_unittest.TestCase):
    """Integration tests: exercise as much code as possible.

    Use cases to test:
    - Nothing needs to be done.
    - Missing file gets created.
    - File with same contents is replaced with link.
    - Excluded files/dirs are skipped.
    - Report unexpected files.
    - Delete unexpected files.
    - Report diffs.
    - Bad arguments are caught.
    - Force deletes existing files and directories.
    - Dry-run.
    """

    def assert_files_are_linked(self, file1: str, file2: str):
        """Assert that two files are linked."""
        self.assertTrue(os.path.samefile(file1, file2))

    @override
    def setUp(self):
        # Do not truncate diffs.
        self.maxDiff: int | None = 1000000
        self.setUpPyfakefs()

    def create_files(self, string: str):
        """Create files in a newline-separated string of files.

        Format:
        - # Comments and empty lines are skipped.
        - file1=file2 => make file2 a hard link to file1.
        - file1->file2 => make file1 a symbolic link to file2.
        - file1 => create file1 with no contents.
        - file1:foo bar baz => create file1 containing "foo bar baz".
        - directory/ => filenames ending in a / create directories.
        It is safe to repeat files, but existing files will not be changed in any
        way so you can't replace the contents of a file.

        Args:
            string: str, string listing files as described above.
        """
        for line in string.split("\n"):
            # Disable "Instance of 'FakeFilesystem' has no 'create_file' member"
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                # Hard link.
                (src, dest) = line.split("=")
                # This allows creating a file with specific contents and then linking it
                # later.
                if not os.path.exists(src):
                    self.fs.create_file(  # pyright: ignore [reportUnknownMemberType]
                        src
                    )
                directory = os.path.dirname(dest)
                if not os.path.exists(directory):
                    os.makedirs(directory)
                os.link(src, dest)
                continue

            if "->" in line:
                # Symbolic link.
                (link, target) = line.split("->")
                directory = os.path.dirname(link)
                if not os.path.exists(directory):
                    os.makedirs(directory)
                os.symlink(target, link)
                continue

            if ":" in line:
                (filename, contents) = line.split(":")
            else:
                (filename, contents) = (line, "")
            if os.path.exists(filename):
                continue
            if filename.endswith(os.sep):
                os.makedirs(filename)
            else:
                self.fs.create_file(  # pyright: ignore [reportUnknownMemberType]
                    filename, contents=contents
                )

    def test_nothing_changes(self):
        """Nothing needs to be done."""
        src_file = "/a/b/c/file"
        dest_file = "/z/y/x/file"
        self.create_files(f"{src_file}={dest_file}")
        self.assert_files_are_linked(src_file, dest_file)

        linkdirs.real_main(
            argv=["linkdirs", os.path.dirname(src_file), os.path.dirname(dest_file)]
        )
        self.assert_files_are_linked(src_file, dest_file)

    def test_git_subdirectory_is_ignored(self):
        """.git isn't linked, testing that --ignore_pattern works."""
        src_dir = "/a/b/c/dir"
        dest_dir = "/z/y/x/dir"
        files = f"""
        {src_dir}/.git/config:pretend config
        {dest_dir}/
        """
        self.create_files(files)

        linkdirs.real_main(argv=["linkdirs", src_dir, dest_dir])
        self.assertFalse(os.path.exists(os.path.join(dest_dir, ".git", "config")))

    def test_dest_perms_unchanged(self):
        """Destination directory perms don't change unnecessarily."""
        src_dir = "/a/b/c/dir"
        dest_dir = "/z/y/x/dir"
        files = f"""
        {src_dir}/
        {dest_dir}/
        """
        self.create_files(files)
        mode = int("0755", base=8)
        os.chmod(src_dir, mode)
        os.chmod(dest_dir, mode)

        with mock.patch.object(os, "chmod") as fake_chmod:
            linkdirs.real_main(
                argv=["linkdirs", os.path.dirname(src_dir), os.path.dirname(dest_dir)]
            )
            fake_chmod.assert_not_called()

    def test_dest_perms_are_changed(self):
        """Destination directory perms change if necessary."""
        src_dir = "/a/b/c/dir"
        dest_dir = "/z/y/x/dir"
        src_mode = int("0755", base=8)
        dest_mode = int("0700", base=8)
        os.makedirs(src_dir)
        os.makedirs(dest_dir)
        os.chmod(src_dir, src_mode)
        os.chmod(dest_dir, src_mode)
        subdirs = ["1", "2", "3", "4"]
        for subdir in subdirs:
            s_dir = os.path.join(src_dir, subdir)
            d_dir = os.path.join(dest_dir, subdir)
            os.makedirs(s_dir)
            os.chmod(s_dir, src_mode)
            os.makedirs(d_dir)
            if int(subdir) % 2 == 0:
                os.chmod(d_dir, dest_mode)
            else:
                os.chmod(d_dir, src_mode)

        linkdirs.real_main(
            argv=["linkdirs", os.path.dirname(src_dir), os.path.dirname(dest_dir)]
        )
        self.assertEqual(src_mode, stat.S_IMODE(os.stat(dest_dir).st_mode))
        for subdir in subdirs:
            d_dir = os.path.join(dest_dir, subdir)
            self.assertEqual(src_mode, stat.S_IMODE(os.stat(d_dir).st_mode))

    def test_missing_file_is_created(self):
        """Missing file gets created."""
        src_file = "/a/b/c/file"
        self.create_files(f"{src_file}:qwerty")

        dest_file = "/z/y/x/file"
        linkdirs.real_main(
            argv=["linkdirs", os.path.dirname(src_file), os.path.dirname(dest_file)]
        )
        self.assert_files_are_linked(src_file, dest_file)

    def test_source_dir_replaced_once(self):
        """/src/foo/src/bar => /dest/foo/src/bar, not /dest/foo/dest/bar."""
        src_file = "/a/b/foo/a/b/file"
        self.create_files(f"{src_file}:qwerty")

        dest_file = "/z/y/foo/a/b/file"
        linkdirs.real_main(argv=["linkdirs", "/a/b", "/z/y"])
        self.assert_files_are_linked(src_file, dest_file)

    def test_replace_same_contents(self):
        """File with same contents is replaced with link."""
        src_file = "/a/b/c/file"
        dest_file = "/z/y/x/file"
        self.create_files(f"{src_file}:qwerty")
        self.create_files(f"{dest_file}:qwerty")

        with mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout:
            linkdirs.real_main(
                argv=["linkdirs", os.path.dirname(src_file), os.path.dirname(dest_file)]
            )
            self.assert_files_are_linked(src_file, dest_file)
            expected = (
                "/a/b/c/file and /z/y/x/file are different files but have the"
                " same contents; deleting and linking\n"
            )
            self.assertMultiLineEqual(expected, mock_stdout.getvalue())

    def test_skip_symlinks(self):
        """Symlinks are ignored when requested."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        os.makedirs(src_dir)
        os.makedirs(dest_dir)
        os.symlink(
            os.path.join(src_dir, "sym-source"), os.path.join(src_dir, "sym-dest")
        )

        with mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout:
            linkdirs.real_main(
                argv=["linkdirs", "--ignore_symlinks", src_dir, dest_dir]
            )
            actual = mock_stdout.getvalue()
            self.assertFalse("Skipping symbolic link" in actual)

    def test_report_unexpected_files(self):
        """Report unexpected files."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file
        # 'asdf' subdir exists here, so it will be checked in dest_dir.
        {src_dir}/asdf/file
        {src_dir}/asdf/ignore-some/dont-ignore
        {dest_dir}/asdf/ignore-some/dont-ignore
        {dest_dir}/pinky
        {dest_dir}/the_brain
        # Ensure there is a subdir that should not be reported.
        {dest_dir}/subdir/
        # And also a subdir that will be reported.
        {dest_dir}/asdf/report_me/
        # Ignore this file and directory.
        {dest_dir}/asdf/ignore-some/should-be-ignored/a-file
        {dest_dir}/asdf/delete dir with spaces/delete file with spaces
        # Symlink that should be skipped
        {dest_dir}/symlink-to-skip -> /tmp/foo
        # Symlink that should be reported
        {dest_dir}/asdf/symlink-to-report->/tmp/foo
        """
        self.create_files(files)

        skip_filename = "skip-me"
        skip_contents = """
        ignore-some/should-be-ignored
        """
        with open(skip_filename, "w", encoding="utf8") as skip_fh:
            skip_fh.write(skip_contents)

        actual = linkdirs.real_main(
            argv=[
                "linkdirs",
                "--report_unexpected_files",
                "--ignore_unexpected_children",
                f"--ignore_file={skip_filename}",
                src_dir,
                dest_dir,
            ]
        )
        # TODO: change this to a multi-line string?
        expected = [
            "Unexpected directory: /z/y/x/asdf/delete dir with spaces",
            "Unexpected directory: /z/y/x/asdf/report_me",
            "Unexpected file: /z/y/x/asdf/delete dir with spaces/delete "
            + "file with spaces",
            "Unexpected file: /z/y/x/asdf/symlink-to-report",
            "Unexpected file: /z/y/x/pinky",
            "Unexpected file: /z/y/x/the_brain",
            "rm '/z/y/x/asdf/delete dir with spaces/delete file with spaces' "
            + "/z/y/x/asdf/symlink-to-report /z/y/x/pinky /z/y/x/the_brain",
            "rmdir '/z/y/x/asdf/delete dir with spaces' /z/y/x/asdf/report_me",
        ]
        self.assertEqual(expected, actual)
        # Unexpected files should not be deleted.
        self.assertTrue(os.path.exists("/z/y/x/the_brain"))

    def test_delete_unexpected_files(self):
        """Delete unexpected files."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file
        # 'asdf' subdir exists here, so it will be checked in dest_dir.
        {src_dir}/asdf/file
        {dest_dir}/pinky
        {dest_dir}/the_brain
        # Ensure there is a subdir that should not be reported.
        {dest_dir}/subdir/
        # Symlink that should be skipped
        {dest_dir}/symlink-to-skip->/tmp/foo
        # Symlink that should be deleted
        {dest_dir}/asdf/symlink-to-delete->/tmp/foo
        """
        self.create_files(files)

        actual = linkdirs.real_main(
            argv=[
                "linkdirs",
                "--delete_unexpected_files",
                "--ignore_unexpected_children",
                src_dir,
                dest_dir,
            ]
        )
        self.assertEqual([], actual)
        # Unexpected files should be deleted.
        self.assertFalse(os.path.exists("/z/y/x/the_brain"))
        self.assertFalse(os.path.exists("/z/y/x/pinky"))
        self.assertTrue(os.path.lexists("/z/y/x/symlink-to-skip"))
        self.assertFalse(os.path.lexists("/z/y/x/asdf/symlink-to-delete"))

    def test_delete_unexp_keeps_dirs(self):
        """Delete unexpected files but not directories."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file
        # 'asdf' subdir exists here, so it will be checked in dest_dir.
        {src_dir}/asdf/file
        {dest_dir}/pinky
        {dest_dir}/the_brain
        # Ensure there is a subdir that should not be reported.
        {dest_dir}/subdir/
        # And also subdirs that will be reported.
        {dest_dir}/asdf/report_me/
        {dest_dir}/asdf/report_me_too/
        """
        self.create_files(files)

        actual = linkdirs.real_main(
            argv=[
                "linkdirs",
                "--delete_unexpected_files",
                "--ignore_unexpected_children",
                src_dir,
                dest_dir,
            ]
        )
        expected = [
            "Refusing to delete directories without --force/-f:"
            + " /z/y/x/asdf/report_me /z/y/x/asdf/report_me_too",
            "Unexpected directory: /z/y/x/asdf/report_me",
            "Unexpected directory: /z/y/x/asdf/report_me_too",
            "rmdir /z/y/x/asdf/report_me_too /z/y/x/asdf/report_me",
        ]
        self.assertEqual(expected, actual)
        # Unexpected files should be deleted.
        self.assertFalse(os.path.exists("/z/y/x/the_brain"))
        self.assertFalse(os.path.exists("/z/y/x/pinky"))
        # But not unexpected directories.
        self.assertTrue(os.path.exists("/z/y/x/asdf/report_me"))

    def test_force_removes_unexp_dirs(self):
        """Delete unexpected files and directories with --force."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file
        # 'asdf' subdir exists here, so it will be checked in dest_dir.
        {src_dir}/asdf/file
        {dest_dir}/pinky
        {dest_dir}/the_brain
        # Ensure there is a subdir that should not be reported.
        {dest_dir}/subdir/
        # And also a subdir that will be removed.
        {dest_dir}/asdf/delete_me/
        # And create a nested subdir that will be removed.  This ensures that nested
        # subdirs are handled correctly, i.e. we don't delete the parent and then
        # fail to delete the child.
        {dest_dir}/asdf/delete_me/delete_me_too/
        """
        self.create_files(files)

        actual = linkdirs.real_main(
            argv=[
                "linkdirs",
                "--delete_unexpected_files",
                "--ignore_unexpected_children",
                "--force",
                src_dir,
                dest_dir,
            ]
        )
        self.assertEqual([], actual)
        # Unexpected files should be deleted.
        self.assertFalse(os.path.exists("/z/y/x/the_brain"))
        self.assertFalse(os.path.exists("/z/y/x/pinky"))
        # And unexpected directories.
        self.assertFalse(os.path.exists("/z/y/x/asdf/delete_me"))

    def test_exclusions_are_skipped(self):
        """Excluded files/dirs are skipped."""
        src_dir = "/a/b/c"
        files = f"""
        {src_dir}/harry/link_me
        {src_dir}/harry/me_too
        {src_dir}/murphy/link_me
        {src_dir}/murphy/me_too
        {src_dir}/ignore/subdir-link/test3
        # Everything below here is excluded so should not be linked.
        {src_dir}/harry/ignore-me1
        {src_dir}/harry/ignore-me2
        {src_dir}/harry/ignore-me3
        {src_dir}/harry/pinky
        {src_dir}/harry/the_brain
        {src_dir}/loki/link_me
        {src_dir}/loki/me_too
        {src_dir}/loki/pinky
        {src_dir}/loki/the_brain
        {src_dir}/molly/link_me
        {src_dir}/molly/me_too
        {src_dir}/molly/pinky
        {src_dir}/molly/the_brain
        {src_dir}/murphy/pinky
        {src_dir}/murphy/the_brain
        {src_dir}/ignore/subdir/test1
        {src_dir}/ignore/subdir/test2
        """
        self.create_files(files)

        skip_filename = "skip-me"
        skip_contents = """
        # Files to skip.
        pinky
        the_brain
        # Directories to skip.
        loki
        molly
        # Patterns to skip.
        ignore-me*
        # foo/bar should be ignored
        ignore/subdir
        """
        with open(skip_filename, "w", encoding="utf8") as skip_fh:
            skip_fh.write(skip_contents)

        dest_dir = "/z/y/x"
        linkdirs.real_main(
            argv=[
                "linkdirs",
                f"--ignore_file={skip_filename}",
                # Report unexpected files because it exercises more code
                # paths.
                "--report_unexpected_files",
                "--ignore_unexpected_children",
                src_dir,
                dest_dir,
            ]
        )

        files = []
        for dirpath, _unused_x, filenames in os.walk(dest_dir):
            for filename in filenames:
                files.append(  # pyright: ignore [reportUnknownMemberType]
                    os.path.join(dirpath, filename)
                )
        files.sort()  # pyright: ignore [reportUnknownMemberType]
        expected = [
            "harry/link_me",
            "harry/me_too",
            "ignore/subdir-link/test3",
            "murphy/link_me",
            "murphy/me_too",
        ]
        expected = [os.path.join(dest_dir, x) for x in expected]
        self.assertEqual(expected, files)

    def test_report_diffs(self):
        """Report diffs."""
        src_file = "/a/b/c/file"
        dest_file = "/z/y/x/file"
        files = f"""
        {src_file}:qwerty
        {dest_file}:asdf
        """
        self.create_files(files)

        # Test without --force to generate diffs.
        actual = linkdirs.real_main(
            argv=["linkdirs", os.path.dirname(src_file), os.path.dirname(dest_file)]
        )
        # Strip off timestamps.
        actual = [re.sub(r"\t.*$", "\t", x) for x in actual]
        expected = [
            f"--- {dest_file}\t",
            f"+++ {src_file}\t",
            "@@ -1 +1 @@",
            "-asdf",
            "+qwerty",
        ]
        self.assertEqual(expected, actual)

        # Test with --force to overwrite.
        actual = linkdirs.real_main(
            argv=[
                "linkdirs",
                "--force",
                os.path.dirname(src_file),
                os.path.dirname(dest_file),
            ]
        )
        self.assertEqual([], actual)
        self.assert_files_are_linked(src_file, dest_file)

    def test_argument_handling(self):
        """Bad arguments are caught."""
        self.assertEqual(
            ["linkdirs [OPTIONS] SOURCE_DIRECTORY [...] DESTINATION_DIRECTORY"],
            linkdirs.real_main(argv=["linkdirs", "--force", "/asdf"]),
        )
        expected = [
            "Cannot enable --delete_unexpected_files without "
            + "--ignore_unexpected_children"
        ]
        actual = linkdirs.real_main(
            argv=["linkdirs", "--delete_unexpected_files", "/asdf", "/qwerty"]
        )
        self.assertEqual(expected, actual)

    def test_force_deletes_dest(self):
        """Force deletes existing files and directories."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file1:qwerty
        {src_dir}/file2:asdf
        {src_dir}/file3:pinky
        {src_dir}/dir1/file4
        {dest_dir}/file1:12345
        {dest_dir}/file2/
        {dest_dir}/file3:pinky
        # Subdir in src, file in dest.
        {dest_dir}/dir1:pinky
        """
        self.create_files(files)

        with mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout:
            messages = linkdirs.real_main(
                argv=["linkdirs", "--force", src_dir, dest_dir]
            )
            self.assertEqual([], messages)
            self.assertEqual("", mock_stdout.getvalue())
            for filename in ["file1", "file2", "file3", "dir1/file4"]:
                self.assert_files_are_linked(
                    os.path.join(src_dir, filename), os.path.join(dest_dir, filename)
                )

    def test_dryrun(self):
        """Dry-run."""
        src_dir = "/a/b/c"
        dest_dir = "/z/y/x"
        files = f"""
        {src_dir}/file1:qwerty
        {src_dir}/file2:asdf
        {src_dir}/file3:pinky
        {src_dir}/file4:brain
        {src_dir}/file5:3 links
        # Test handling a subdir that exists in dest_dir.
        {src_dir}/dir1/file1
        # Test handling a subdir that does not exist in dest_dir.
        {src_dir}/dir2/file1
        # Test handling a destination that isn't a subdir in dest_dir.
        {src_dir}/dir3/file1
        {src_dir}/dir4/file1
        # Test handling a file that is already linked.
        {src_dir}/already-linked={dest_dir}/already-linked

        {dest_dir}/file1:12345
        {dest_dir}/file3:pinky
        # Test handling a destination that isn't a file.
        {dest_dir}/file4/
        # Test handling of multiply linked destination files.
        {dest_dir}/file5:3 links
        {dest_dir}/file5={dest_dir}/file5-file5
        # Test handling of subdirectories.
        {dest_dir}/dir1/
        # Test handling a destination that isn't a subdir.
        {dest_dir}/dir3
        {dest_dir}/dir4
        """
        self.create_files(files)
        # Set permissions on source directory so they differ from destination directory
        # to check that permissions are reset correctly.
        os.chmod(f"{src_dir}/dir1", 0o700)
        # Test handling of source symlinks - not supported by create_files().
        os.symlink(os.path.join(src_dir, "file5"), os.path.join(src_dir, "file6"))
        os.symlink(os.path.join(src_dir, "file7"), os.path.join(src_dir, "file8"))

        with mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout:
            messages = linkdirs.real_main(
                argv=["linkdirs", "--dryrun", src_dir, dest_dir]
            )
            # Strip off timestamps.
            messages = [re.sub(r"\t.*$", "\t", x) for x in messages]
            expected = [
                "--- /z/y/x/file1\t",
                "+++ /a/b/c/file1\t",
                "@@ -1 +1 @@",
                "-12345",
                "+qwerty",
                "/z/y/x/dir3 is not a directory",
                "/z/y/x/dir4 is not a directory",
                "/z/y/x/file4: is not a file",
                "/z/y/x/file5: link count is 2; is this file present in multiple "
                + "source directories?",
                "Skipping symbolic link /a/b/c/file6",
                "Skipping symbolic link /a/b/c/file8",
            ]
            self.assertEqual(expected, messages)
            self.assertFalse(
                os.path.samefile(
                    os.path.join(src_dir, "file1"), os.path.join(dest_dir, "file1")
                )
            )
            self.assertTrue(os.path.exists(os.path.join(dest_dir, "file1")))
            self.assertFalse(os.path.exists(os.path.join(dest_dir, "file2")))
            self.assertTrue(os.path.exists(os.path.join(dest_dir, "file3")))
            self.assertFalse(os.path.isdir(os.path.join(dest_dir, "dir2")))
            stdout = "\n".join(
                [
                    "chmod 0700 /z/y/x/dir1",
                    "mkdir /z/y/x/dir2",
                    "ln /a/b/c/file2 /z/y/x/file2",
                    "/a/b/c/file3 and /z/y/x/file3 are different files but have the"
                    + " same contents; deleting and linking",
                    "rm /z/y/x/file3",
                    "ln /a/b/c/file3 /z/y/x/file3",
                    "ln /a/b/c/dir1/file1 /z/y/x/dir1/file1",
                    "ln /a/b/c/dir2/file1 /z/y/x/dir2/file1",
                    "ln /a/b/c/dir3/file1 /z/y/x/dir3/file1",
                    "ln /a/b/c/dir4/file1 /z/y/x/dir4/file1",
                    "",
                ]
            )
            self.assertMultiLineEqual(stdout, mock_stdout.getvalue())


class TestUsage(unittest.TestCase):
    """Tests for usage messages."""

    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    @mock.patch.object(sys, "stderr", new_callable=io.StringIO)
    def test_no_args(
        self,
        mock_stderr: io.StringIO,
        mock_stdout: io.StringIO,
        _unused_mock_exit: mock.Mock,
    ):
        """Test no args."""
        linkdirs.real_main(argv=["argv0"])
        self.assertEqual("", mock_stdout.getvalue())
        # The name of the program is pytest when running tests.
        expected = (
            "usage: pytest [OPTIONS] SOURCE_DIRECTORY [...] DESTINATION_DIRECTORY\n"
            "pytest: error: the following arguments are required: DIRECTORIES\n"
        )
        self.assertEqual(expected, mock_stderr.getvalue().replace("pytest-3", "pytest"))

    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_help(self, mock_stdout: io.StringIO, _unused_mock_exit: mock.Mock):
        """Test --help to ensure that the description is correctly set up."""
        linkdirs.real_main(argv=["argv0", "--help"])
        # The name of the program is pytest when running tests.
        substrings = [
            "usage: pytest [OPTIONS] SOURCE_DIRECTORY [...] ",
            "Link all files in SOURCE_DIRECTORY",
            "positional arguments: DIRECTORIES See usage for details",
            "--dryrun Perform a trial run with no changes made (default: False)",
            "--force Remove existing files if necessary (default: False)",
            "--ignore_file FILENAME File containing shell patterns to ignore.",
            "--ignore_pattern FILENAME Extra shell patterns to ignore",
            "['CVS', '.git', '.gitignore', '.gitmodules', '.hg', '.svn', '*.swp']",
            "--ignore_unexpected_children When checking for unexpected files or",
            "--report_unexpected_files Report unexpected files in"
            + " DESTINATION_DIRECTORY (default: False)",
            "--delete_unexpected_files Delete unexpected files in"
            + " DESTINATION_DIRECTORY (default: False)",
        ]
        # The position of newlines depends on the width of the terminal, so remove
        # them for consistency.  Likewise spaces.
        stdout = mock_stdout.getvalue().replace("\n", " ").replace("pytest-3", "pytest")
        stdout = re.sub(r"\s+", " ", stdout)
        for substring in substrings:
            with self.subTest(f"Testing -->>{substring}<<--"):
                self.assertIn(substring, stdout)
        # Check that the description is set up properly.
        self.assertRegex(
            stdout,
            r"^usage: pytest .OPTIONS. SOURCE_DIRECTORY ....."
            + r" DESTINATION_DIRECTORY Link all files in SOURCE_DIRECTORY"
            + r" .SOURCE_DIRECTORY.... to DESTINATION_DIRECTORY, creating the"
            + r" destination directory hierarchy where",
        )


class TestMisc(fake_filesystem_unittest.TestCase):
    """Tests for code that can't otherwise be tested."""

    @override
    def setUp(self):
        self.setUpPyfakefs()

    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_safe_unlink_prints(self, mock_stdout: io.StringIO):
        """Integration tests cannot make safe_unlink print for directories."""
        test_dir = linkdirs.Path("/a/b/c")
        os.makedirs(test_dir)
        linkdirs.safe_unlink(unlink_me=test_dir, dryrun=True)
        self.assertEqual(f"rm -r {test_dir}\n", mock_stdout.getvalue())

    @mock.patch.object(os.path, "islink")
    def test_safe_unlink_race_condition(self, mock_islink: mock.Mock):
        """Pretend a file exists to test deletion race condition handling."""
        mock_islink.return_value = True
        # An exception will be raised if the code doesn't handle the missing file
        # correctly.
        linkdirs.safe_unlink(unlink_me=linkdirs.Path("/does-not-exist"), dryrun=False)

    def test_read_skip_patterns(self):
        """Test that patterns are read correctly."""
        filename = linkdirs.Path("ignore-file")
        contents = (
            textwrap.dedent(
                """
        # Comments should be skipped.
        foo
        bar*baz
        dir/subdir
        # Empty lines should be skipped
        """
            ).strip()
            + "\n\n"
        )
        self.fs.create_file(  # pyright: ignore [reportUnknownMemberType]
            filename, contents=contents
        )
        expected = ["foo", "bar*baz", "dir/subdir"]
        actual = linkdirs.read_skip_patterns_from_file(filename=filename)
        self.assertEqual(expected, actual)


if __name__ == "__main__":  # pragma: no mutate
    unittest.main()
