import os
import sys
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import make_rust_github_workflow


class TestMakeGithubWorkflow(unittest.TestCase):
    def test_generate_release_workflow(self) -> None:
        """Tests that the release workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_release_workflow.template"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections and program name replacement
        self.assertIn("name: Release", content)
        self.assertIn(f"bin: {program_name}", content)

    def test_generate_publish_workflow(self) -> None:
        """Tests that the publish workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_publish_workflow.template"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_publish_workflow.template)
        self.assertIn("name: CI and Release", content)
        self.assertIn("name: Publish to Crates.io", content)

    def test_generate_workflow_with_completions(self) -> None:
        """Tests that shell completions are included when requested for release."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_release_workflow.template", output_shell_completion=True
        )

        # Check for shebang with flag
        self.assertTrue(
            content.startswith(
                "#!/usr/bin/env -S make_rust_github_workflow.py testapp "
                + "--output_shell_completion"
            )
        )

        # Check for shell completion block
        self.assertIn("# 1.1 Generate shell completions", content)


class TestMain(fake_filesystem_unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Ensure the template files exist in the fake filesystem
        template_dir = os.path.dirname(
            os.path.realpath(make_rust_github_workflow.__file__)
        )
        for template in [
            "rust_release_workflow.template",
            "rust_publish_workflow.template",
        ]:
            template_path = os.path.join(template_dir, template)
            self.fs.add_real_file(  # pyright: ignore [reportUnknownMemberType]
                template_path
            )

    @mock.patch.object(sys, "argv", ["make_rust_github_workflow.py", "cliapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly writes both files."""
        make_rust_github_workflow.main()
        release_file = ".github/workflows/release.yml"
        publish_file = ".github/workflows/publish.yml"
        self.assertTrue(os.path.exists(release_file))
        self.assertTrue(os.path.exists(publish_file))

        with open(release_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: Release", content)

        with open(publish_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: CI and Release", content)

    @mock.patch.object(
        sys, "argv", ["make_rust_github_workflow.py", "cliapp", "workflow.yml"]
    )
    def test_main_with_explicit_release_file(self) -> None:
        """Tests that main respects explicit file and puts publish in the same dir."""
        make_rust_github_workflow.main()
        self.assertTrue(os.path.exists("workflow.yml"))
        self.assertTrue(os.path.exists("publish.yml"))


if __name__ == "__main__":
    unittest.main()
