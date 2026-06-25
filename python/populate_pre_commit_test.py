"""Tests for populate_pre_commit.py."""

import os
import pathlib
import subprocess
import textwrap
from typing import cast, override
import unittest
from unittest import mock

import pyfakefs.fake_filesystem_unittest

import populate_pre_commit


class TestShouldInclude(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for the should_include_* detection functions."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def create_file(
        self, file_path: pathlib.Path | str, contents: str | bytes = ""
    ) -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_should_include_actionlint(self) -> None:
        self.assertFalse(
            populate_pre_commit.should_include_actionlint(frozenset[str]())
        )
        self.assertTrue(
            populate_pre_commit.should_include_actionlint(
                frozenset[str]({".github/workflows/ci.yaml"})
            )
        )

    def test_should_include_actionlint_yml(self) -> None:
        """Tests should_include_actionlint with .yml files."""
        self.assertTrue(
            populate_pre_commit.should_include_actionlint(
                frozenset[str]({".github/workflows/ci.yml"})
            )
        )

    def test_has_extension(self) -> None:
        """Tests the has_extension function."""
        self.assertFalse(populate_pre_commit.has_extension(frozenset[str](), ".md"))
        self.assertTrue(
            populate_pre_commit.has_extension(frozenset[str]({"README.md"}), ".md")
        )
        self.assertFalse(
            populate_pre_commit.has_extension(frozenset[str]({"README.txt"}), ".md")
        )
        self.assertTrue(
            populate_pre_commit.has_extension(frozenset[str]({"main.py"}), ".py")
        )
        self.assertTrue(
            populate_pre_commit.has_extension(frozenset[str]({"data.json"}), ".json")
        )
        self.assertTrue(
            populate_pre_commit.has_extension(frozenset[str]({"config.toml"}), ".toml")
        )

    def test_should_include_shellcheck(self) -> None:
        self.assertFalse(
            populate_pre_commit.should_include_shellcheck(frozenset[str]())
        )
        self.assertTrue(
            populate_pre_commit.should_include_shellcheck(frozenset[str]({"script.sh"}))
        )

    def test_should_include_shellcheck_shebang(self) -> None:
        """Tests should_include_shellcheck with extension-less shell scripts."""
        self.create_file("deploy", contents="#!/bin/bash\necho hello\n")
        self.assertTrue(
            populate_pre_commit.should_include_shellcheck(frozenset[str]({"deploy"}))
        )

    def test_should_include_shellcheck_non_shell_shebang(self) -> None:
        """Tests should_include_shellcheck with non-shell shebang."""
        self.create_file("main", contents="#!/usr/bin/env python3\nprint('hi')\n")
        self.assertFalse(
            populate_pre_commit.should_include_shellcheck(frozenset[str]({"main"}))
        )

    def test_is_shell_script_not_file(self) -> None:
        """Tests is_shell_script with a directory path."""
        pathlib.Path("dir").mkdir()
        self.assertFalse(populate_pre_commit.is_shell_script(pathlib.Path("dir")))

    def test_is_shell_script_no_shebang(self) -> None:
        """Tests is_shell_script with a file that has no shebang."""
        self.create_file("plain", contents="no shebang here\n")
        self.assertFalse(populate_pre_commit.is_shell_script(pathlib.Path("plain")))

    def test_is_shell_script_unicode_error(self) -> None:
        """Tests is_shell_script with a binary file that triggers UnicodeDecodeError."""
        self.create_file("binary", contents=b"\xff\xfe\xfd")
        self.assertFalse(populate_pre_commit.is_shell_script(pathlib.Path("binary")))

    def test_shebang_present_but_dot_in_filename(self) -> None:
        """Tests should_include_shellcheck with non-shell shebang."""
        self.create_file("main.txt", contents="#!/bin/sh\necho foo\n")
        self.assertFalse(
            populate_pre_commit.should_include_shellcheck(frozenset[str]({"main.txt"}))
        )

    def test_should_include_golang_files(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_golang(frozenset[str]()))
        self.assertTrue(
            populate_pre_commit.should_include_golang(frozenset[str]({"main.go"}))
        )

    def test_should_include_golang_mod(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_golang(frozenset[str]()))
        self.assertTrue(
            populate_pre_commit.should_include_golang(frozenset[str]({"go.mod"}))
        )

    def test_should_include_json(self) -> None:
        """Tests the should_include_json function."""
        self.assertFalse(populate_pre_commit.should_include_json(frozenset[str]()))
        self.assertTrue(
            populate_pre_commit.should_include_json(frozenset[str]({"data.json"}))
        )
        self.assertFalse(
            populate_pre_commit.should_include_json(
                frozenset[str]({".vscode/settings.json"})
            )
        )
        self.assertTrue(
            populate_pre_commit.should_include_json(
                frozenset[str]({"data.json", ".vscode/settings.json"})
            )
        )

    def test_should_include_readme_toc(self) -> None:
        """Tests the should_include_readme_toc function."""
        self.assertFalse(
            populate_pre_commit.should_include_readme_toc(frozenset[str]())
        )
        self.assertTrue(
            populate_pre_commit.should_include_readme_toc(frozenset[str]({"README.md"}))
        )
        self.assertFalse(
            populate_pre_commit.should_include_readme_toc(
                frozenset[str]({"subdir/README.md"})
            )
        )

    def test_should_include_rust_files(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_rust(frozenset[str]()))
        self.assertTrue(
            populate_pre_commit.should_include_rust(frozenset[str]({"src/main.rs"}))
        )

    def test_should_include_rust_toml(self) -> None:
        self.assertFalse(populate_pre_commit.should_include_rust(frozenset[str]()))
        self.assertTrue(
            populate_pre_commit.should_include_rust(frozenset[str]({"Cargo.toml"}))
        )


class TestPopulatePreCommit(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for the main populate_pre_commit function."""

    mock_snippets: list[tuple[str, bool]] = []

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Add the real snippets directory to the fake filesystem
        self.fs.add_real_directory(  # pyright: ignore[reportUnknownMemberType]
            populate_pre_commit.SNIPPETS_DIR
        )

        # Patch the module-level constants and functions
        self.enterContext(
            mock.patch.object(
                populate_pre_commit,
                "get_non_ignored_files",
                return_value=frozenset[str](),
            )
        )
        self.enterContext(
            mock.patch.object(
                populate_pre_commit,
                "get_git_root",
                return_value=".",
            )
        )
        self.enterContext(
            mock.patch.object(
                os,
                "chdir",
            )
        )

        self.mock_snippets = [
            # keep-sorted start
            ("ignored.yaml", False),
            ("meta.yaml", True),
            ("python.yaml", True),
            # keep-sorted end
        ]

    def create_file(self, file_path: pathlib.Path | str, contents: str = "") -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_creates_new_file(self) -> None:
        self.assertFalse(pathlib.Path(".pre-commit-config.yaml").exists())
        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit_test.py",
            snippets=self.mock_snippets,
        )
        self.assertTrue(pathlib.Path(".pre-commit-config.yaml").exists())

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks:
                - id: check-hooks-apply
              # managed-by-populate-pre-commit end: meta.yaml
              # managed-by-populate-pre-commit start: python.yaml
              - repo: https://github.com/pre-commit/pre-commit-hooks
                rev: v6.0.0
                hooks:
                - id: debug-statements
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

        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit_test.py",
            snippets=[("meta.yaml", True)],
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks:
                - id: check-hooks-apply
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

        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit_test.py",
            snippets=[("meta.yaml", True)],
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks:
                - id: check-hooks-apply
              # managed-by-populate-pre-commit end: meta.yaml
              - repo: custom-repo
            """)
        self.assertEqual(content, expected)

    def test_adds_repos_if_missing(self) -> None:
        self.create_file(".pre-commit-config.yaml", contents="# Just a comment\n")

        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit_test.py",
            snippets=[("meta.yaml", True)],
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = textwrap.dedent("""\
            #!/usr/bin/env -S "populate_pre_commit_test.py"
            # Just a comment
            repos:
              # managed-by-populate-pre-commit start: meta.yaml
              - repo: meta
                hooks:
                - id: check-hooks-apply
              # managed-by-populate-pre-commit end: meta.yaml
            """)
        self.assertEqual(content, expected)

    def test_empty_snippet_file_crashes(self) -> None:
        """Tests that an empty snippet file crashes the program."""
        self.create_file(".pre-commit-config.yaml", contents="repos:\n")

        empty_path = populate_pre_commit.SNIPPETS_DIR / "empty.yaml"
        self.create_file(empty_path, contents="")
        with self.assertRaisesRegex(
            ValueError, f"config snippet {empty_path} is empty"
        ):
            populate_pre_commit.populate_pre_commit(
                extra_args={},
                script_file="populate_pre_commit_test.py",
                snippets=[("empty.yaml", True)],
            )

    def test_missing_snippet_file_crashes(self) -> None:
        """Tests that a missing snippet file crashes the program."""
        self.create_file(".pre-commit-config.yaml", contents="repos:\n")

        with self.assertRaisesRegex(OSError, "really_missing.yaml"):
            populate_pre_commit.populate_pre_commit(
                extra_args={},
                script_file="populate_pre_commit_test.py",
                snippets=[("really_missing.yaml", True)],
            )

    def test_extra_args_injection(self) -> None:
        """Tests that extra arguments are correctly injected into snippets."""
        extra_args = {"debug-statements": "--flag1 --flag2"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args,
            script_file="populate_pre_commit_test.py",
            snippets=self.mock_snippets,
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        self.assertIn("- id: debug-statements", content)
        self.assertIn("args:", content)
        self.assertIn("- --flag1", content)
        self.assertIn("- --flag2", content)

    def test_shebang_generation(self) -> None:
        """Tests that the shebang line is correctly generated."""
        extra_args = {"hook1": "val1"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args,
            script_file="populate_pre_commit.py",
            snippets=self.mock_snippets,
        )

        with open(".pre-commit-config.yaml", "r") as f:
            lines = f.readlines()

        self.assertTrue(lines[0].startswith("#!/usr/bin/env -S"))
        self.assertIn('--extra-arg\\_"hook1=val1"', lines[0])

    def test_shebang_escaping(self) -> None:
        """Tests that spaces in extra arguments are correctly escaped in the shebang."""
        extra_args = {"hook 1": "val 1"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args,
            script_file="populate_pre_commit.py",
            snippets=self.mock_snippets,
        )
        with open(".pre-commit-config.yaml", "r") as f:
            shebang = f.readline()
        self.assertIn("hook\\_1=val\\_1", shebang)

    def test_executable_bit(self) -> None:
        """Tests that the generated file is marked as executable."""
        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit.py",
            snippets=self.mock_snippets,
        )
        mode = pathlib.Path(".pre-commit-config.yaml").stat().st_mode
        self.assertTrue(bool(mode & 0o111))

    def test_main_success(self) -> None:
        """Tests the main function with arguments."""
        with mock.patch(
            "sys.argv", ["populate_pre_commit.py", "--extra-arg", "hook1=args"]
        ):
            with mock.patch("populate_pre_commit.populate_pre_commit") as mock_populate:
                populate_pre_commit.main()
                mock_populate.assert_called_once_with(
                    extra_args={"hook1": "args"},
                    script_file=mock.ANY,
                    snippets=mock.ANY,
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
        config_path = pathlib.Path(".pre-commit-config.yaml")
        if config_path.exists():
            config_path.unlink()
        populate_pre_commit.populate_pre_commit(
            extra_args={}, script_file="script.py", snippets=self.mock_snippets
        )
        self.assertTrue(config_path.exists())
        with config_path.open("r", encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("#!"))

    def test_replaces_existing_shebang(self) -> None:
        """Tests that an existing shebang line is replaced."""
        initial_content = "#!/old/shebang\nrepos:\n"
        self.create_file(".pre-commit-config.yaml", contents=initial_content)
        populate_pre_commit.populate_pre_commit(
            extra_args={}, script_file="new_script.py", snippets=self.mock_snippets
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

    def test_apply_extra_args_hook_with_existing_args(self) -> None:
        """Tests apply_extra_args when the hook ID is found and has existing 'args'."""
        content = textwrap.dedent("""\
            - repo: local
              hooks:
              - id: hook1
                args:
                - --existing
            """)
        expected = textwrap.dedent("""\
            - repo: local
              hooks:
              - id: hook1
                args:
                - --existing
                - --flag1
                - --flag2
            """)
        self.assertEqual(
            populate_pre_commit.apply_extra_args(content, {"hook1": "--flag1 --flag2"}),
            expected,
        )

    def test_apply_extra_args_hook_no_existing_args(self) -> None:
        """Tests apply_extra_args when the hook ID is found but does not have 'args'."""
        content = textwrap.dedent("""\
            - repo: local
              hooks:
              - id: hook1
            """)
        expected = textwrap.dedent("""\
            - repo: local
              hooks:
              - id: hook1
                args:
                - --flag1
                - --flag2
            """)
        self.assertEqual(
            populate_pre_commit.apply_extra_args(content, {"hook1": "--flag1 --flag2"}),
            expected,
        )

    def test_multiple_snippets_with_extra_args(self) -> None:
        """Tests multiple snippets with extra arguments."""
        mock_snippets = [
            ("python.yaml", True),
            ("meta.yaml", True),
        ]
        extra_args = {"debug-statements": "--flag1", "check-hooks-apply": "--flag2"}
        populate_pre_commit.populate_pre_commit(
            extra_args=extra_args,
            script_file="populate_pre_commit_test.py",
            snippets=mock_snippets,
        )

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        # Check that flags are in the YAML content (indented)
        self.assertIn("- --flag1", content)
        self.assertIn("- --flag2", content)
        # Check that they are also in the shebang
        self.assertIn("debug-statements=--flag1", content)
        self.assertIn("check-hooks-apply=--flag2", content)

    def test_main_no_extra_args(self) -> None:
        """Tests the main function without extra arguments."""
        with mock.patch("sys.argv", ["populate_pre_commit.py"]):
            with mock.patch("populate_pre_commit.populate_pre_commit") as mock_populate:
                populate_pre_commit.main()
                mock_populate.assert_called_once_with(
                    extra_args={}, script_file=mock.ANY, snippets=mock.ANY
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
        populate_pre_commit.populate_pre_commit(
            extra_args={},
            script_file="populate_pre_commit_test.py",
            snippets=[("meta.yaml", True)],
        )
        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()
        self.assertIn("# Top comment", content)
        self.assertIn("# Bottom comment", content)


class TestGetNonIgnoredFiles(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for get_non_ignored_files."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def create_file(self, file_path: pathlib.Path | str, contents: str = "") -> None:
        self.fs.create_file(  # pyright: ignore[reportUnknownMemberType]
            file_path, contents=contents
        )

    def test_basic_files(self) -> None:
        self.create_file("file1.txt")
        self.create_file("dir1/file2.txt")
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            files = populate_pre_commit.get_non_ignored_files()
        self.assertEqual(files, frozenset[str]({"file1.txt", "dir1/file2.txt"}))

    def test_local_gitignore(self) -> None:
        self.create_file(".gitignore", contents="ignored.txt\n")
        self.create_file("file1.txt")
        self.create_file("ignored.txt")
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            files = populate_pre_commit.get_non_ignored_files()
        self.assertEqual(files, frozenset[str]({".gitignore", "file1.txt"}))

    def test_git_info_exclude(self) -> None:
        self.create_file(".git/info/exclude", contents="*.log\n")
        self.create_file("test.log")
        self.create_file("test.txt")
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            files = populate_pre_commit.get_non_ignored_files()
        self.assertEqual(files, frozenset[str]({"test.txt"}))

    def test_global_ignore(self) -> None:
        home_ignore = pathlib.Path("~/.gitignore.global").expanduser()
        self.create_file(home_ignore, contents="venv/\n")
        self.create_file("venv/bin/python")
        self.create_file("main.py")
        mock_ret = cast(
            mock.MagicMock,
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_ret.stdout = "~/.gitignore.global\n"
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = mock_ret
            files = populate_pre_commit.get_non_ignored_files()
        self.assertIn("main.py", files)

    def test_global_ignore_fallback(self) -> None:
        home_ignore = pathlib.Path("~/.config/git/ignore").expanduser()
        self.create_file(home_ignore, contents="build/\n")
        self.create_file("build/output.o")
        self.create_file("src/main.c")
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            files = populate_pre_commit.get_non_ignored_files()
        self.assertIn("src/main.c", files)
        self.assertNotIn("build/output.o", files)

    def test_pruning_directories(self) -> None:
        self.create_file(".gitignore", contents="node_modules/\n")
        self.create_file("node_modules/pkg/index.js")
        self.create_file("src/index.js")
        with mock.patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            files = populate_pre_commit.get_non_ignored_files()
        self.assertIn("src/index.js", files)
        self.assertNotIn("node_modules/pkg/index.js", files)


class TestGetGitRoot(pyfakefs.fake_filesystem_unittest.TestCase):
    """Tests for the get_git_root function."""

    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def test_get_git_root_success(self) -> None:
        """Tests get_git_root when git command succeeds."""
        mock_completed_process = cast(
            subprocess.CompletedProcess[str],
            mock.create_autospec(subprocess.CompletedProcess, instance=True),
        )
        mock_completed_process.stdout = "/repo/root\n"
        with mock.patch.object(
            subprocess, "run", return_value=mock_completed_process
        ) as mock_run:
            root = populate_pre_commit.get_git_root()
            self.assertEqual(root, "/repo/root")
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_get_git_root_failure(self) -> None:
        """Tests that get_git_root raises an error when git command fails."""
        with mock.patch.object(
            subprocess, "run", side_effect=subprocess.CalledProcessError(1, "git")
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                populate_pre_commit.get_git_root()


if __name__ == "__main__":
    unittest.main()
