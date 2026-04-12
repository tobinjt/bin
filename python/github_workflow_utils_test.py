"""Tests for github_workflow_utils.py."""

import os
import unittest
from typing import override

from pyfakefs import fake_filesystem_unittest

import github_workflow_utils


class TestArgs(unittest.TestCase):
    """Tests for the Args class."""

    def test_init_defaults(self) -> None:
        """Tests that Args initializes with correct defaults."""
        args = github_workflow_utils.Args()
        self.assertEqual(args.program_name, "")
        self.assertIsNone(args.ignored_filename)

    def test_init_custom(self) -> None:
        """Tests that Args initializes with provided values."""
        args = github_workflow_utils.Args(
            program_name="foo",
            ignored_filename="bar.py",
        )
        self.assertEqual(args.program_name, "foo")
        self.assertEqual(args.ignored_filename, "bar.py")


class TestGetParser(unittest.TestCase):
    """Tests for the get_parser function."""

    def test_get_parser(self) -> None:
        """Tests that get_parser returns a properly configured parser."""
        parser = github_workflow_utils.get_parser("Test description")
        args = parser.parse_args(
            ["myprog", "ignoreme.py"],
            namespace=github_workflow_utils.Args(),
        )
        self.assertEqual(args.program_name, "myprog")
        self.assertEqual(args.ignored_filename, "ignoreme.py")


class TestWorkflowUtils(fake_filesystem_unittest.TestCase):
    """Tests for workflow generation and writing functions."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def test_generate_workflow_basic(self) -> None:
        """Tests basic workflow generation."""
        script_dir = "/fake/path"
        script_file = os.path.join(script_dir, "my_script.py")
        template_name = "test.template"
        template_path = os.path.join(script_dir, template_name)

        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            template_path, contents="Hello PROGRAM_NAME!\nINSERT_HERE\nGoodbye."
        )

        content = github_workflow_utils.generate_workflow(
            program_name="my_app",
            template_name=template_name,
            script_file=script_file,
        )

        self.assertTrue(content.startswith("#!/usr/bin/env -S my_script.py my_app\n"))
        self.assertIn("Hello my_app!", content)
        self.assertNotIn("completion_script", content)

    def test_write_workflow(self) -> None:
        """Tests that write_workflow creates directories and sets permissions."""
        output_file = "/fake/out/dir/workflow.yml"
        github_workflow_utils.write_workflow(output_file, "content")

        self.assertTrue(os.path.exists(output_file))
        with open(output_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "content\n")

        st = os.stat(output_file)
        self.assertEqual(st.st_mode & 0o777, 0o755)


if __name__ == "__main__":
    unittest.main()
