"""Tests for make_github_workflows.py."""

import os
import pathlib
import unittest
from typing import cast, override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import get_git_root
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

    def create_file(self, file_path: str, contents: str = "") -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_generate_workflow_basic(self) -> None:
        """Tests basic workflow generation."""
        script_dir = "/fake/path"
        script_file = str(pathlib.Path(script_dir) / "my_script.py")
        template_name = "test.template"
        template_path = str(pathlib.Path(script_dir) / "workflows" / template_name)

        self.create_file(template_path, contents="Hello!\nINSERT_HERE\nGoodbye.")

        content = make_github_workflows.generate_workflow(
            template_name=template_name,
            script_file=script_file,
        )

        self.assertTrue(content.startswith('#!/usr/bin/env -S "my_script.py"\n'))
        self.assertIn("Hello!", content)

    def test_write_workflow(self) -> None:
        """Tests that write_workflow creates directories and sets permissions."""
        output_file = "/fake/out/dir/workflow.yml"
        make_github_workflows.write_workflow(output_file, "content")

        self.assertTrue(pathlib.Path(output_file).exists())
        with open(output_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "content\n")

        st = os.stat(output_file)
        self.assertEqual(st.st_mode & 0o777, 0o755)

    def test_generate_dependabot_config(self) -> None:
        """Tests dependabot config generation with various ecosystems."""
        script_dir = "/fake/path"
        script_file = str(pathlib.Path(script_dir) / "my_script.py")
        template_path = str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml")

        dependabot_template = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "github-actions"},
                {"package-ecosystem": "gomod"},
                {"package-ecosystem": "cargo"},
                {"package-ecosystem": "pip"},
                {"package-ecosystem": "composer"},
                {"package-ecosystem": "npm"},
            ],
        }
        self.create_file(
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
        self.assertNotIn("package-ecosystem: composer", content)
        self.assertNotIn("package-ecosystem: npm", content)
        self.assertTrue(content.startswith('#!/usr/bin/env -S "my_script.py"\n'))

        # 2. Add go.mod. gomod should now be included.
        self.create_file("go.mod")
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file,
            extra_args={"foo": "bar"},
        )
        self.assertIn("package-ecosystem: gomod", content)
        self.assertTrue(
            content.startswith(
                '#!/usr/bin/env -S "my_script.py"\\_--extra-arg\\_"foo=bar"\n'
            )
        )

        # 3. Add Cargo.toml. cargo should now be included.
        self.create_file("Cargo.toml")
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: cargo", content)

        # 4. Add python directory. pip should now be included.
        self.create_file("python/dummy.py")
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: pip", content)

        # 5. Add composer.json. composer should now be included.
        self.create_file("composer.json")
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: composer", content)

        # 6. Add package.json. npm should now be included.
        self.create_file("package.json")
        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        self.assertIn("package-ecosystem: npm", content)

    def test_main(self) -> None:
        """Tests the main orchestration function."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "golang_pre-commit.yml"),
            contents="GOLANG_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )

        # Create a trigger file to activate Go language
        self.create_file("go.mod")

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
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

            # Assert that zizmor.yaml was copied
            zizmor_dest = pathlib.Path(".github/zizmor.yaml")
            self.assertTrue(zizmor_dest.exists())
            self.assertEqual(zizmor_dest.read_text(encoding="utf-8"), "ZIZMOR_CONTENT")

            # Assert that actionlint.yaml was copied
            actionlint_dest = pathlib.Path(".github/actionlint.yaml")
            self.assertTrue(actionlint_dest.exists())
            self.assertEqual(
                actionlint_dest.read_text(encoding="utf-8"), "ACTIONLINT_CONTENT"
            )

    def test_generate_workflow_with_extra_args(self) -> None:
        """Tests workflow generation with extra arguments."""
        script_dir = "/fake/path"
        script_file = str(pathlib.Path(script_dir) / "my_script.py")
        template_name = "test.template"
        template_path = str(pathlib.Path(script_dir) / "workflows" / template_name)

        self.create_file(
            template_path, contents="run: cargo llvm-cov test\nrun: other command"
        )

        extra_args = {"cargo llvm-cov test": "--foo --bar"}
        content = make_github_workflows.generate_workflow(
            template_name=template_name,
            script_file=script_file,
            extra_args=extra_args,
        )

        self.assertTrue(
            content.startswith(
                '#!/usr/bin/env -S "my_script.py"\\_--extra-arg\\_"cargo\\_llvm-cov\\_test=--foo\\_--bar"\n'
            )
        )
        self.assertIn("run: cargo llvm-cov test --foo --bar", content)
        self.assertIn("run: other command", content)

    def test_main_with_extra_args(self) -> None:
        """Tests the main orchestration function with extra arguments."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "rust_pull_request.yml"),
            contents="run: cargo llvm-cov test",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "rust_security_audit.yml"),
            contents="RUST_AUDIT_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )

        self.create_file("Cargo.toml")

        args = make_github_workflows.Args(
            extra_args=["cargo llvm-cov test=--foo"],
        )

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=args,
            ),
            mock.patch.object(
                make_github_workflows, "write_workflow"
            ) as mock_write_workflow,
        ):
            make_github_workflows.main()

            # Let's find the call for rust_pull_request.yml
            rust_pr_call = next(
                call
                for call in mock_write_workflow.call_args_list
                if call.args[0] == ".github/workflows/rust_pull_request.yml"
            )
            self.assertIn(
                "run: cargo llvm-cov test --foo", cast(str, rust_pr_call.args[1])
            )

            # Assert that zizmor.yaml was copied
            zizmor_dest = pathlib.Path(".github/zizmor.yaml")
            self.assertTrue(zizmor_dest.exists())
            self.assertEqual(zizmor_dest.read_text(encoding="utf-8"), "ZIZMOR_CONTENT")

            # Assert that actionlint.yaml was copied
            actionlint_dest = pathlib.Path(".github/actionlint.yaml")
            self.assertTrue(actionlint_dest.exists())
            self.assertEqual(
                actionlint_dest.read_text(encoding="utf-8"), "ACTIONLINT_CONTENT"
            )

    def test_main_invalid_extra_arg(self) -> None:
        """Tests that main raises ValueError for invalid --extra-arg format."""
        args = make_github_workflows.Args(
            extra_args=["invalid_format"],
        )

        with mock.patch.object(
            make_github_workflows.argparse.ArgumentParser,
            "parse_args",
            return_value=args,
        ):
            with self.assertRaises(ValueError) as cm:
                make_github_workflows.main()
            self.assertIn("Invalid --extra-arg format", str(cm.exception))

    def test_generate_dependabot_config_unknown_ecosystem(self) -> None:
        """Tests dependabot config generation with an unknown ecosystem."""
        script_dir = "/fake/path"
        script_file = str(pathlib.Path(script_dir) / "my_script.py")
        template_path = str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml")

        dependabot_template = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "unknown"},
            ],
        }
        self.create_file(
            template_path, contents=make_github_workflows.yaml.dump(dependabot_template)
        )

        content = make_github_workflows.generate_dependabot_config(
            script_file=script_file
        )
        # unknown should be filtered out
        self.assertNotIn("package-ecosystem: unknown", content)

    def test_check_hugo_johntobin_ie_no_file(self) -> None:
        """Tests check_hugo_johntobin_ie when config.toml does not exist."""
        self.assertFalse(make_github_workflows.check_hugo_johntobin_ie())

    def test_check_hugo_johntobin_ie_wrong_content(self) -> None:
        """Tests check_hugo_johntobin_ie when config.toml has incorrect content."""
        self.create_file("config.toml", contents='baseURL = "https://example.com"\n')
        self.assertFalse(make_github_workflows.check_hugo_johntobin_ie())

    def test_check_hugo_johntobin_ie_correct_content(self) -> None:
        """Tests check_hugo_johntobin_ie when config.toml is correct."""
        self.create_file(
            "config.toml",
            contents='baseURL = "https://www.johntobin.ie/"\n',
        )
        self.assertTrue(make_github_workflows.check_hugo_johntobin_ie())

    def test_check_hugo_johntobin_ie_oserror(self) -> None:
        """Tests check_hugo_johntobin_ie when open raises OSError."""
        self.create_file("config.toml")
        with mock.patch.object(pathlib.Path, "open", side_effect=OSError("Read error")):
            self.assertFalse(make_github_workflows.check_hugo_johntobin_ie())

    def test_main_with_hugo_johntobin_ie(self) -> None:
        """Tests main generating the Hugo workflow when config.toml is correct."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "hugo-johntobin.ie.yml"),
            contents="HUGO_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )
        self.create_file(
            "config.toml",
            contents='baseURL = "https://www.johntobin.ie/"\n',
        )

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
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
            # 3. .github/workflows/hugo-johntobin.ie.yml
            self.assertEqual(mock_write_workflow.call_count, 3)
            mock_write_workflow.assert_any_call(".github/dependabot.yml", mock.ANY)
            mock_write_workflow.assert_any_call(
                ".github/workflows/dependabot_validation.yml", mock.ANY
            )
            mock_write_workflow.assert_any_call(
                ".github/workflows/hugo-johntobin.ie.yml", mock.ANY
            )

            # Assert that zizmor.yaml was copied
            zizmor_dest = pathlib.Path(".github/zizmor.yaml")
            self.assertTrue(zizmor_dest.exists())
            self.assertEqual(zizmor_dest.read_text(encoding="utf-8"), "ZIZMOR_CONTENT")

            # Assert that actionlint.yaml was copied
            actionlint_dest = pathlib.Path(".github/actionlint.yaml")
            self.assertTrue(actionlint_dest.exists())
            self.assertEqual(
                actionlint_dest.read_text(encoding="utf-8"), "ACTIONLINT_CONTENT"
            )

    def test_get_all_workflows(self) -> None:
        """Tests that get_all_workflows returns all expected workflows."""
        workflows = make_github_workflows.get_all_workflows()
        self.assertIn(
            make_github_workflows.Workflow(
                "dependabot_validation.yml",
                ".github/workflows/dependabot_validation.yml",
            ),
            workflows,
        )
        self.assertIn(
            make_github_workflows.Workflow(
                "golang_pre-commit.yml",
                ".github/workflows/golang_pre-commit.yml",
            ),
            workflows,
        )
        self.assertIn(
            make_github_workflows.Workflow(
                "rust_pull_request.yml",
                ".github/workflows/rust_pull_request.yml",
            ),
            workflows,
        )
        self.assertIn(
            make_github_workflows.Workflow(
                "rust_security_audit.yml",
                ".github/workflows/rust_security_audit.yml",
            ),
            workflows,
        )
        self.assertIn(
            make_github_workflows.Workflow(
                "python_pre-commit.yml",
                ".github/workflows/python_pre-commit.yml",
            ),
            workflows,
        )
        self.assertIn(
            make_github_workflows.Workflow(
                "hugo-johntobin.ie.yml",
                ".github/workflows/hugo-johntobin.ie.yml",
            ),
            workflows,
        )

    def test_remove_workflow_exists(self) -> None:
        """Tests that remove_workflow calls git rm when the file exists."""
        output_file = ".github/workflows/rust_pull_request.yml"
        self.create_file(output_file, contents="STALE_CONTENT")
        with mock.patch.object(make_github_workflows.subprocess, "run") as mock_run:
            make_github_workflows.remove_workflow(output_file)
            mock_run.assert_called_once_with(
                ["git", "rm", output_file],
                check=True,
            )

    def test_remove_workflow_not_exists(self) -> None:
        """Tests that remove_workflow does not call git rm if file does not exist."""
        output_file = ".github/workflows/rust_pull_request.yml"
        with mock.patch.object(make_github_workflows.subprocess, "run") as mock_run:
            make_github_workflows.remove_workflow(output_file)
            mock_run.assert_not_called()

    def test_main_removes_unneeded_workflow(self) -> None:
        """Tests that main removes an unneeded workflow if it exists."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "golang_pre-commit.yml"),
            contents="GOLANG_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )

        # Create trigger file to activate Go language
        self.create_file("go.mod")

        # Create an existing workflow that SHOULD NOT be removed because Go is active
        existing_needed = ".github/workflows/golang_pre-commit.yml"
        self.create_file(existing_needed, contents="EXISTING_GO_CONTENT")

        # Create an unneeded workflow that SHOULD be removed
        unneeded_workflow = ".github/workflows/rust_pull_request.yml"
        self.create_file(unneeded_workflow, contents="STALE_RUST_CONTENT")

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=make_github_workflows.Args(),
            ),
            mock.patch.object(make_github_workflows, "write_workflow"),
            mock.patch.object(make_github_workflows.subprocess, "run") as mock_run,
        ):
            make_github_workflows.main()

            mock_run.assert_called_once_with(
                ["git", "rm", unneeded_workflow],
                check=True,
            )

    def test_main_removes_multiple_unneeded_workflows(self) -> None:
        """Tests that main removes multiple unneeded workflows if they exist."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "golang_pre-commit.yml"),
            contents="GOLANG_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )

        # Create trigger file to activate Go language
        self.create_file("go.mod")

        rust_workflow = ".github/workflows/rust_pull_request.yml"
        python_workflow = ".github/workflows/python_pre-commit.yml"
        self.create_file(rust_workflow, contents="STALE_RUST")
        self.create_file(python_workflow, contents="STALE_PYTHON")

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=make_github_workflows.Args(),
            ),
            mock.patch.object(make_github_workflows, "write_workflow"),
            mock.patch.object(make_github_workflows.subprocess, "run") as mock_run,
        ):
            make_github_workflows.main()

            self.assertEqual(mock_run.call_count, 2)
            mock_run.assert_any_call(["git", "rm", python_workflow], check=True)
            mock_run.assert_any_call(["git", "rm", rust_workflow], check=True)

    def test_main_no_languages_keeps_dependabot_validation(self) -> None:
        """Tests that main keeps dependabot_validation.yml even without language triggers."""
        script_file = make_github_workflows.__file__
        script_dir = str(pathlib.Path(script_file).parent)
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot.yml"),
            contents="version: 2\nupdates: []",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "dependabot_validation.yml"),
            contents="VALIDATION_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "zizmor.yaml"),
            contents="ZIZMOR_CONTENT",
        )
        self.create_file(
            str(pathlib.Path(script_dir) / "workflows" / "actionlint.yaml"),
            contents="ACTIONLINT_CONTENT",
        )

        # No language triggers exist (e.g. no go.mod, Cargo.toml, requirements.txt, etc.)
        # Existing python workflow in destination should be deleted
        python_dest = ".github/workflows/python_pre-commit.yml"
        self.create_file(python_dest, contents="STALE_PYTHON")

        # Existing dependabot_validation in destination should be kept
        dependabot_val_dest = ".github/workflows/dependabot_validation.yml"
        self.create_file(dependabot_val_dest, contents="EXISTING_VALIDATION")

        with (
            mock.patch.object(
                get_git_root,
                "get_git_root",
                return_value=".",
            ),
            mock.patch.object(
                make_github_workflows.argparse.ArgumentParser,
                "parse_args",
                return_value=make_github_workflows.Args(),
            ),
            mock.patch.object(
                make_github_workflows, "write_workflow"
            ) as mock_write_workflow,
            mock.patch.object(make_github_workflows.subprocess, "run") as mock_run,
        ):
            make_github_workflows.main()

            # write_workflow was called for dependabot.yml and dependabot_validation.yml
            self.assertEqual(mock_write_workflow.call_count, 2)
            mock_write_workflow.assert_any_call(".github/dependabot.yml", mock.ANY)
            mock_write_workflow.assert_any_call(
                ".github/workflows/dependabot_validation.yml", mock.ANY
            )

            # git rm was only called for python_pre-commit.yml, NOT dependabot_validation.yml
            mock_run.assert_called_once_with(["git", "rm", python_dest], check=True)


if __name__ == "__main__":
    unittest.main()
