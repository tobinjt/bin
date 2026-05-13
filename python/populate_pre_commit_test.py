"""Tests for populate_pre_commit.py."""

import os
import textwrap
from typing import override
import unittest
from unittest import mock

import pyfakefs.fake_filesystem_unittest

import populate_pre_commit


class TestShouldInclude(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for the should_include_* detection functions."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def create_file(self, file_path: str, contents: str = "") -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_should_include_actionlint(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_actionlint())
        self.create_file(".github/workflows/ci.yaml")
        self.assertTrue(populate_pre_commit.should_include_actionlint())

    def test_should_include_actionlint_yml(self) -> None:
        """Tests should_include_actionlint with .yml files."""
        self.create_file(".github/workflows/ci.yml")
        self.assertTrue(populate_pre_commit.should_include_actionlint())

    def test_should_include_markdownlint(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_markdownlint())
        self.create_file("README.md")
        self.assertTrue(populate_pre_commit.should_include_markdownlint())

    def test_should_include_shellcheck(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_shellcheck())
        self.create_file("script.sh")
        self.assertTrue(populate_pre_commit.should_include_shellcheck())

    def test_should_include_python(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_python())
        self.create_file("main.py")
        self.assertTrue(populate_pre_commit.should_include_python())

    def test_should_include_golang_files(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_golang())
        self.create_file("main.go")
        self.assertTrue(populate_pre_commit.should_include_golang())

    def test_should_include_golang_mod(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_golang())
        self.create_file("go.mod")
        self.assertTrue(populate_pre_commit.should_include_golang())

    def test_should_include_rust_files(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_rust())
        self.create_file("src/main.rs")
        self.assertTrue(populate_pre_commit.should_include_rust())

    def test_should_include_rust_toml(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_rust())
        self.create_file("Cargo.toml")
        self.assertTrue(populate_pre_commit.should_include_rust())


class TestPopulatePreCommit(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for the main populate_pre_commit function."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Mock SNIPPETS_DIR to be within the fake filesystem
        snippets_dir = "/fake/snippets"
        self.fs.create_dir(snippets_dir)  # pyright: ignore[reportUnknownMemberType]

        # Create some fake snippets
        self.create_file(
            os.path.join(snippets_dir, "meta.yaml"),
            contents="- repo: meta\n  hooks: []\n",
        )
        self.create_file(
            os.path.join(snippets_dir, "python.yaml"),
            contents="- repo: local\n  hooks:\n  - id: fake-python\n    args: []\n",
        )

        # Patch the module-level constants
        self.enterContext(
            mock.patch.object(populate_pre_commit, "SNIPPETS_DIR", snippets_dir)
        )

        mock_snippets = (
            # keep-sorted start
            ("ignored.yaml", lambda: False),
            ("meta.yaml", lambda: True),
            ("python.yaml", lambda: True),
            # keep-sorted end
        )
        self.enterContext(
            mock.patch.object(populate_pre_commit, "SNIPPETS", mock_snippets)
        )

    def create_file(self, file_path: str, contents: str = "") -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_creates_new_file(self) -> None:
        self.assertFalse(os.path.exists(".pre-commit-config.yaml"))
        populate_pre_commit.populate_pre_commit(
            extra_args={}, script_file="populate_pre_commit_test.py"
        )
        self.assertTrue(os.path.exists(".pre-commit-config.yaml"))

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks: []
              # managed-by-populate-pre-commit end: meta.yaml
              # managed-by-populate-pre-commit start: python.yaml
              - repo: local
                hooks:
                - id: fake-python
                  args: []
              # managed-by-populate-pre-commit end: python.yaml
            """)
        self.assertEqual(content, expected)

    def test_updates_existing_file_preserves_custom(self) -> None:
        initial_content = textwrap.dedent("""\
            repos:
              - repo: custom-repo
                hooks:
                  - id: custom-hook
            """)
        self.create_file(".pre-commit-config.yaml", contents=initial_content)

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit(
                extra_args={}, script_file="populate_pre_commit_test.py"
            )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks: []
              # managed-by-populate-pre-commit end: meta.yaml
              - repo: custom-repo
                hooks:
                  - id: custom-hook
            """)
        self.assertEqual(content, expected)

    def test_replaces_existing_managed_blocks(self) -> None:
        initial_content = textwrap.dedent("""\
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: old-meta-stuff
              # managed-by-populate-pre-commit end: meta.yaml
              - repo: custom-repo
            """)
        self.create_file(".pre-commit-config.yaml", contents=initial_content)

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit(
                extra_args={}, script_file="populate_pre_commit_test.py"
            )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks: []
              # managed-by-populate-pre-commit end: meta.yaml
              - repo: custom-repo
            """)
        self.assertEqual(content, expected)

    def test_adds_repos_if_missing(self) -> None:
        self.create_file(".pre-commit-config.yaml", contents="# Just a comment\n")

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit(
                extra_args={}, script_file="populate_pre_commit_test.py"
            )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            # Just a comment
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks: []
              # managed-by-populate-pre-commit end: meta.yaml
            """)
        self.assertEqual(content, expected)

    def test_empty_snippet_file_crashes(self) -> None:
        """Tests that an empty snippet file crashes the program."""
        self.create_file(".pre-commit-config.yaml", contents="repos:\n")

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("empty.yaml", lambda: True)]
        ):
            self.create_file(
                os.path.join(populate_pre_commit.SNIPPETS_DIR, "empty.yaml"),
                contents="",
            )
            with self.assertRaisesRegex(
                ValueError, "config snippet /fake/snippets/empty.yaml is empty"
            ):
                populate_pre_commit.populate_pre_commit(
                    extra_args={}, script_file="populate_pre_commit_test.py"
                )

    def test_missing_snippet_file_crashes(self) -> None:
        """Tests that a missing snippet file crashes the program."""
        self.create_file(".pre-commit-config.yaml", contents="repos:\n")

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("really_missing.yaml", lambda: True)]
        ):
            with self.assertRaisesRegex(OSError, "really_missing.yaml"):
                populate_pre_commit.populate_pre_commit(
                    extra_args={}, script_file="populate_pre_commit_test.py"
                )

    def test_extra_args_injection(self) -> None:
        """Tests that extra arguments are correctly injected into snippets."""
        extra_args = {"fake-python": "--flag1 --flag2"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args, script_file="populate_pre_commit_test.py"
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        self.assertIn("- id: fake-python", content)
        self.assertIn("args:", content)
        self.assertIn("- --flag1", content)
        self.assertIn("- --flag2", content)

    def test_shebang_generation(self) -> None:
        """Tests that the shebang line is correctly generated."""
        extra_args = {"hook1": "val1"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args, script_file="populate_pre_commit.py"
        )

        with open(".pre-commit-config.yaml", "r") as f:
            lines = f.readlines()

        self.assertTrue(lines[0].startswith("#!/usr/bin/env -S"))
        self.assertIn('--extra-arg\\_"hook1=val1"', lines[0])

    def test_shebang_escaping(self) -> None:
        """Tests that spaces in extra arguments are correctly escaped in the shebang."""
        extra_args = {"hook 1": "val 1"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args, script_file="populate_pre_commit.py"
        )
        with open(".pre-commit-config.yaml", "r") as f:
            shebang = f.readline()
        self.assertIn("hook\\_1=val\\_1", shebang)

    def test_executable_bit(self) -> None:
        """Tests that the generated file is marked as executable."""
        populate_pre_commit.populate_pre_commit(
            extra_args={}, script_file="populate_pre_commit.py"
        )
        mode = os.stat(".pre-commit-config.yaml").st_mode
        self.assertTrue(bool(mode & 0o111))

    def test_main_success(self) -> None:
        """Tests the main function with arguments."""
        with mock.patch(
            "sys.argv", ["populate_pre_commit.py", "--extra-arg", "hook1=args"]
        ):
            with mock.patch("populate_pre_commit.populate_pre_commit") as mock_populate:
                populate_pre_commit.main()
                mock_populate.assert_called_once_with(
                    extra_args={"hook1": "args"}, script_file=mock.ANY
                )

    def test_main_invalid_extra_arg(self) -> None:
        """Tests the main function with invalid --extra-arg format."""
        with mock.patch(
            "sys.argv", ["populate_pre_commit.py", "--extra-arg", "invalid"]
        ):
            with self.assertRaises(ValueError):
                populate_pre_commit.main()

    def test_escape_for_env_s(self) -> None:
        """Tests the escape_for_env_s function."""
        self.assertEqual(populate_pre_commit.escape_for_env_s("\\"), "\\\\")
        self.assertEqual(populate_pre_commit.escape_for_env_s('"'), '\\"')
        self.assertEqual(populate_pre_commit.escape_for_env_s(" "), r"\_")

    def test_populate_pre_commit_no_config_with_script(self) -> None:
        """Tests populate_pre_commit when no config exists but script_file is provided."""
        if os.path.exists(".pre-commit-config.yaml"):
            os.remove(".pre-commit-config.yaml")
        populate_pre_commit.populate_pre_commit(extra_args={}, script_file="script.py")
        self.assertTrue(os.path.exists(".pre-commit-config.yaml"))
        with open(".pre-commit-config.yaml", "r") as f:
            self.assertTrue(f.readline().startswith("#!"))

    def test_replaces_existing_shebang(self) -> None:
        """Tests that an existing shebang line is replaced."""
        initial_content = "#!/old/shebang\nrepos:\n"
        self.create_file(".pre-commit-config.yaml", contents=initial_content)
        populate_pre_commit.populate_pre_commit(
            extra_args={}, script_file="new_script.py"
        )
        with open(".pre-commit-config.yaml", "r") as f:
            first_line = f.readline()
        self.assertIn("new_script.py", first_line)
        self.assertNotIn("old/shebang", first_line)

    def test_build_shebang_args_multiple(self) -> None:
        """Tests build_shebang_args with multiple arguments."""
        extra_args = {"b": "2", "a": "1"}
        result = populate_pre_commit.build_shebang_args(extra_args)
        # Should be sorted by key
        self.assertEqual(result, '\\_--extra-arg\\_"a=1"\\_--extra-arg\\_"b=2"')

    def test_apply_extra_args_hook_not_found(self) -> None:
        """Tests apply_extra_args when the hook ID is not found in the content."""
        content = "- repo: local\n  hooks:\n  - id: hook1\n"
        self.assertEqual(
            populate_pre_commit.apply_extra_args(content, {"hook2": "args"}), content
        )

    def test_multiple_snippets_with_extra_args(self) -> None:
        """Tests multiple snippets with extra arguments."""
        mock_snippets = [
            ("python.yaml", lambda: True),
            ("meta.yaml", lambda: True),
        ]
        extra_args = {"fake-python": "--flag1", "meta-hook": "--flag2"}
        with mock.patch.object(populate_pre_commit, "SNIPPETS", mock_snippets):
            populate_pre_commit.populate_pre_commit(
                extra_args=extra_args, script_file="populate_pre_commit_test.py"
            )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()
        self.assertIn("--flag1", content)

    def test_main_no_extra_args(self) -> None:
        """Tests the main function without extra arguments."""
        with mock.patch("sys.argv", ["populate_pre_commit.py"]):
            with mock.patch("populate_pre_commit.populate_pre_commit") as mock_populate:
                populate_pre_commit.main()
                mock_populate.assert_called_once_with(
                    extra_args={}, script_file=mock.ANY
                )

    def test_build_shebang_args_empty_dict(self) -> None:
        """Tests build_shebang_args with an empty dictionary."""
        self.assertEqual(populate_pre_commit.build_shebang_args({}), "")

    def test_custom_content_preservation(self) -> None:
        """Tests that custom content before and after managed blocks is preserved."""
        initial_content = textwrap.dedent("""\
            # Top comment
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
              # managed-by-populate-pre-commit end: meta.yaml
            # Bottom comment
            """)
        self.create_file(".pre-commit-config.yaml", contents=initial_content)
        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit(
                extra_args={}, script_file="populate_pre_commit_test.py"
            )
        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()
        self.assertIn("# Top comment", content)
        self.assertIn("# Bottom comment", content)


if __name__ == "__main__":
    unittest.main()
