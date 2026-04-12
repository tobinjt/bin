import os
import sys
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import make_rust_github_workflow


class TestMakeGithubWorkflow(unittest.TestCase):
    def test_generate_publish_workflow(self) -> None:
        """Tests that the publish workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_publish_workflow.yml"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_publish_workflow.yml)
        self.assertIn("name: Publish to crates.io if tests pass.", content)
        self.assertIn("name: Cargo Publish", content)

    def test_generate_dependabot_workflow(self) -> None:
        """Tests that the dependabot workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "dependabot.yml"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from dependabot.yml)
        self.assertIn('package-ecosystem: "github-actions"', content)
        self.assertIn('package-ecosystem: "cargo"', content)

    def test_generate_pull_request_workflow(self) -> None:
        """Tests that the PR workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_pull_request_workflow.yml"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_pull_request_workflow.yml)
        self.assertIn("name: Code Quality", content)
        self.assertIn("on:", content)
        self.assertIn("pull_request:", content)

    def test_generate_security_audit_workflow(self) -> None:
        """Tests that the security audit workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_security_audit.yml"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_security_audit.yml)
        self.assertIn("name: Security Audit", content)
        self.assertIn("uses: rustsec/audit-check@v2.0.0", content)


class TestMain(fake_filesystem_unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Ensure the template files exist in the fake filesystem
        template_dir = os.path.dirname(
            os.path.realpath(make_rust_github_workflow.__file__)
        )
        for template in [
            # keep-sorted start
            "dependabot.yml",
            "rust_publish_workflow.yml",
            "rust_pull_request_workflow.yml",
            "rust_security_audit.yml",
            # keep-sorted end
        ]:
            template_path = os.path.join(template_dir, template)
            self.fs.add_real_file(  # pyright: ignore [reportUnknownMemberType]
                template_path
            )

    @mock.patch.object(sys, "argv", ["make_rust_github_workflow.py", "cliapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly writes all files."""
        make_rust_github_workflow.main()
        publish_file = ".github/workflows/rust_publish.yml"
        dependabot_file = ".github/dependabot.yml"
        pull_request_file = ".github/workflows/rust_pull_request.yml"
        security_audit_file = ".github/workflows/rust_security_audit.yml"
        self.assertTrue(os.path.exists(publish_file))
        self.assertTrue(os.path.exists(dependabot_file))
        self.assertTrue(os.path.exists(pull_request_file))
        self.assertTrue(os.path.exists(security_audit_file))

        with open(publish_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: Publish to crates.io if tests pass.", content)

        with open(dependabot_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn('package-ecosystem: "github-actions"', content)
            self.assertIn('package-ecosystem: "cargo"', content)

        with open(pull_request_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: Code Quality", content)

        with open(security_audit_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: Security Audit", content)

    @mock.patch.object(
        sys,
        "argv",
        ["make_rust_github_workflow.py", "cliapp", "extra_ignored_arg"],
    )
    def test_main_with_ignored_arg(self) -> None:
        """Tests that an extra argument is ignored and doesn't cause an error."""
        make_rust_github_workflow.main()
        publish_file = ".github/workflows/rust_publish.yml"
        self.assertTrue(os.path.exists(publish_file))


if __name__ == "__main__":
    unittest.main()
