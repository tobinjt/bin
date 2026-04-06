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
        self.assertIn("name: Build binaries", content)
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
        self.assertIn("name: Publish to crates.io if tests pass.", content)
        self.assertIn("name: Publish to Crates.io", content)

    def test_generate_dependabot_workflow(self) -> None:
        """Tests that the dependabot workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_dependabot.template"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_dependabot.template)
        self.assertIn('package-ecosystem: "github-actions"', content)
        self.assertIn('package-ecosystem: "cargo"', content)

    def test_generate_pull_request_workflow(self) -> None:
        """Tests that the PR workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_pull_request_workflow.template"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_pull_request_workflow.template)
        self.assertIn("name: Code Quality", content)
        self.assertIn("on:", content)
        self.assertIn("pull_request:", content)

    def test_generate_security_audit_workflow(self) -> None:
        """Tests that the security audit workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_security_audit.template"
        )

        # Check for shebang
        self.assertTrue(
            content.startswith("#!/usr/bin/env -S make_rust_github_workflow.py testapp")
        )

        # Check for key sections (from rust_security_audit.template)
        self.assertIn("name: Security Audit", content)
        self.assertIn("uses: rustsec/audit-check@v2.0.0", content)

    def test_generate_workflow_with_completions(self) -> None:
        """Tests that shell completions are included when requested for release."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(
            program_name, "rust_release_workflow.template", output_shell_completion=True
        )

        # Check for shebang with flag
        self.assertTrue(
            content.startswith(
                "#!/usr/bin/env -S make_rust_github_workflow.py "
                + "--output_shell_completion testapp"
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
            "rust_dependabot.template",
            "rust_pull_request_workflow.template",
            "rust_security_audit.template",
        ]:
            template_path = os.path.join(template_dir, template)
            self.fs.add_real_file(  # pyright: ignore [reportUnknownMemberType]
                template_path
            )

    @mock.patch.object(sys, "argv", ["make_rust_github_workflow.py", "cliapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly writes all files."""
        make_rust_github_workflow.main()
        release_file = ".github/workflows/release.yml"
        publish_file = ".github/workflows/publish.yml"
        dependabot_file = ".github/dependabot.yml"
        pull_request_file = ".github/workflows/pull_request.yml"
        security_audit_file = ".github/workflows/security_audit.yml"
        self.assertTrue(os.path.exists(release_file))
        self.assertTrue(os.path.exists(publish_file))
        self.assertTrue(os.path.exists(dependabot_file))
        self.assertTrue(os.path.exists(pull_request_file))
        self.assertTrue(os.path.exists(security_audit_file))

        with open(release_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: Build binaries", content)

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
        ["make_rust_github_workflow.py", "cliapp", "--output_shell_completion"],
    )
    def test_main_with_completions(self) -> None:
        """Tests that main correctly handles the --output_shell_completion flag."""
        make_rust_github_workflow.main()
        release_file = ".github/workflows/release.yml"
        with open(release_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("# 1.1 Generate shell completions", content)

    @mock.patch.object(
        sys,
        "argv",
        ["make_rust_github_workflow.py", "cliapp", "extra_ignored_arg"],
    )
    def test_main_with_ignored_arg(self) -> None:
        """Tests that an extra argument is ignored and doesn't cause an error."""
        make_rust_github_workflow.main()
        release_file = ".github/workflows/release.yml"
        self.assertTrue(os.path.exists(release_file))


if __name__ == "__main__":
    unittest.main()
