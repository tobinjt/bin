"""Tests for make_github_workflows.py."""

import os
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import make_github_workflows


class TestArgs(unittest.TestCase):
    """Tests for the Args class."""

    def test_init_defaults(self) -> None:
        """Tests that Args initializes with correct defaults."""
        args = make_github_workflows.Args()
        self.assertIsNone(args.ignored_filename)

    def test_init_custom(self) -> None:
        """Tests that Args initializes with provided values."""
        args = make_github_workflows.Args(
            ignored_filename="bar.py",
        )
        self.assertEqual(args.ignored_filename, "bar.py")


class TestGetParser(unittest.TestCase):
    """Tests for the get_parser function."""

    def test_get_parser(self) -> None:
        """Tests that get_parser returns a properly configured parser."""
        parser = make_github_workflows.get_parser("Test description")
        args = parser.parse_args(
            ["ignoreme.py"],
            namespace=make_github_workflows.Args(),
        )
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
        template_path = os.path.join(script_dir, "workflows", template_name)

        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            template_path, contents="Hello!\nINSERT_HERE\nGoodbye."
        )

        content = make_github_workflows.generate_workflow(
            template_name=template_name,
            script_file=script_file,
        )

        self.assertTrue(content.startswith("#!/usr/bin/env -S my_script.py\n"))
        self.assertIn("Hello!", content)

    def test_write_workflow(self) -> None:
        """Tests that write_workflow creates directories and sets permissions."""
        output_file = "/fake/out/dir/workflow.yml"
        make_github_workflows.write_workflow(output_file, "content")

        self.assertTrue(os.path.exists(output_file))
        with open(output_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "content\n")

        st = os.stat(output_file)
        self.assertEqual(st.st_mode & 0o777, 0o755)

    def test_generate_dependabot_config(self) -> None:
        """Tests dependabot config generation with various ecosystems."""
        script_dir = "/fake/path"
        script_file = os.path.join(script_dir, "my_script.py")
        template_path = os.path.join(script_dir, "workflows", "dependabot.yml")

        dependabot_template = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "github-actions"},
                {"package-ecosystem": "gomod"},
                {"package-ecosystem": "cargo"},
                {"package-ecosystem": "pip"},
            ],
        }
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            template_path, contents=make_github_workflows.yaml.dump(dependabot_template)
        )

        # 1. No trigger files exist. Only github-actions should be present.
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: github-actions", content)
        self.assertNotIn("package-ecosystem: gomod", content)
        self.assertNotIn("package-ecosystem: cargo", content)
        self.assertNotIn("package-ecosystem: pip", content)

        # 2. Add go.mod. gomod should now be included.
        self.fs.create_file("go.mod")  # pyright: ignore[reportUnknownMemberType]
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: gomod", content)

        # 3. Add Cargo.toml. cargo should now be included.
        self.fs.create_file("Cargo.toml")  # pyright: ignore[reportUnknownMemberType]
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: cargo", content)

        # 4. Add requirements.txt. pip should now be included.
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            "requirements.txt"
        )
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: pip", content)

    def test_main(self) -> None:
        """Tests the main orchestration function."""
        script_file = make_github_workflows.__file__
        script_dir = os.path.dirname(script_file)
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "golang_pre-commit.yml"),
            contents="GOLANG_CONTENT",
        )

        # Create a trigger file to activate Go language
        self.fs.create_file("go.mod")  # pyright: ignore[reportUnknownMemberType]

        with (
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=make_github_workflows.Args(),
            ),
            mock.patch.object(
                make_github_workflows, "write_workflow"
            ) as mock_write_workflow,
        ):
            make_github_workflows.main()

            # Check that write_workflow was called for:
            # 1. .github/dependabot.yml
            # 2. .github/workflows/dependabot_validation.yml
            # 3. .github/workflows/golang_pre-commit.yml
            self.assertEqual(mock_write_workflow.call_count, 3)
            mock_write_workflow.assert_any_call(".github/dependabot.yml", mock.ANY)
            mock_write_workflow.assert_any_call(
                ".github/workflows/dependabot_validation.yml", mock.ANY
            )
            mock_write_workflow.assert_any_call(
                ".github/workflows/golang_pre-commit.yml", mock.ANY
            )

    def test_main_multiple_languages(self) -> None:
        """Tests the main orchestration function with multiple languages."""
        script_file = make_github_workflows.__file__
        script_dir = os.path.dirname(script_file)
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "golang_pre-commit.yml"),
            contents="GOLANG_CONTENT",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "rust_publish.yml"),
            contents="RUST_PUBLISH_CONTENT",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "rust_pull_request.yml"),
            contents="RUST_PR_CONTENT",
        )
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            os.path.join(script_dir, "workflows", "rust_security_audit.yml"),
            contents="RUST_AUDIT_CONTENT",
        )

        # Activate Go and Rust
        self.fs.create_file("go.mod")  # pyright: ignore[reportUnknownMemberType]
        self.fs.create_file("Cargo.toml")  # pyright: ignore[reportUnknownMemberType]

        with (
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=make_github_workflows.Args(),
            ),
            mock.patch.object(
                make_github_workflows, "write_workflow"
            ) as mock_write_workflow,
        ):
            make_github_workflows.main()

            # write_workflow should be called for:
            # 1. .github/dependabot.yml
            # 2. .github/workflows/dependabot_validation.yml (shared)
            # 3. .github/workflows/golang_pre-commit.yml
            # 4. .github/workflows/rust_publish.yml
            # 5. .github/workflows/rust_pull_request.yml
            # 6. .github/workflows/rust_security_audit.yml
            self.assertEqual(mock_write_workflow.call_count, 6)

    def test_generate_dependabot_config_unknown_ecosystem(self) -> None:
        """Tests dependabot config generation with an unknown ecosystem."""
        script_dir = "/fake/path"
        script_file = os.path.join(script_dir, "my_script.py")
        template_path = os.path.join(script_dir, "workflows", "dependabot.yml")

        dependabot_template = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "unknown"},
            ],
        }
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            template_path, contents=make_github_workflows.yaml.dump(dependabot_template)
        )

        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        # unknown should be filtered out
        self.assertNotIn("package-ecosystem: unknown", content)


if __name__ == "__main__":
    unittest.main()
