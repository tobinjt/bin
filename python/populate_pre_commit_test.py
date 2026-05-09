"""Tests for populate_pre_commit.py."""

import os
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
            os.path.join(snippets_dir, "meta.yaml"), contents="- repo: meta\n"
        )
        self.create_file(
            os.path.join(snippets_dir, "local-python.yaml"),
            contents="- repo: local\n\n  hooks:\n    - id: fake-python\n",
        )
        self.create_file(os.path.join(snippets_dir, "missing.yaml"), contents="")

        # Patch the module-level constants
        self.enterContext(
            mock.patch.object(populate_pre_commit, "SNIPPETS_DIR", snippets_dir)
        )

        mock_snippets = (
            # keep-sorted start
            ("ignored.yaml", lambda: False),
            ("local-python.yaml", lambda: True),
            ("meta.yaml", lambda: True),
            ("missing_file.yaml", lambda: True),
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
        populate_pre_commit.populate_pre_commit()
        self.assertTrue(os.path.exists(".pre-commit-config.yaml"))

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = (
            "repos:\n"
            "  # managed-by-populate-pre-commit start: local-python.yaml\n"
            "  - repo: local\n"
            "\n"
            "    hooks:\n"
            "      - id: fake-python\n"
            "  # managed-by-populate-pre-commit end: local-python.yaml\n"
            "  # managed-by-populate-pre-commit start: meta.yaml\n"
            "  - repo: meta\n"
            "  # managed-by-populate-pre-commit end: meta.yaml\n"
        )
        self.assertEqual(content, expected)

    def test_updates_existing_file_preserves_custom(self) -> None:
        initial_content = (
            "repos:\n  - repo: custom-repo\n    hooks:\n      - id: custom-hook\n"
        )
        self.create_file(".pre-commit-config.yaml", contents=initial_content)

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit()

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = (
            "repos:\n"
            "  # managed-by-populate-pre-commit start: meta.yaml\n"
            "  - repo: meta\n"
            "  # managed-by-populate-pre-commit end: meta.yaml\n"
            "  - repo: custom-repo\n"
            "    hooks:\n"
            "      - id: custom-hook\n"
        )
        self.assertEqual(content, expected)

    def test_replaces_existing_managed_blocks(self) -> None:
        initial_content = (
            "repos:\n"
            "  # managed-by-populate-pre-commit start: meta.yaml\n"
            "  - repo: old-meta-stuff\n"
            "  # managed-by-populate-pre-commit end: meta.yaml\n"
            "  - repo: custom-repo\n"
        )
        self.create_file(".pre-commit-config.yaml", contents=initial_content)

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit()

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = (
            "repos:\n"
            "  # managed-by-populate-pre-commit start: meta.yaml\n"
            "  - repo: meta\n"
            "  # managed-by-populate-pre-commit end: meta.yaml\n"
            "  - repo: custom-repo\n"
        )
        self.assertEqual(content, expected)

    def test_adds_repos_if_missing(self) -> None:
        self.create_file(".pre-commit-config.yaml", contents="# Just a comment\n")

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("meta.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit()

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = (
            "# Just a comment\n"
            "repos:\n"
            "  # managed-by-populate-pre-commit start: meta.yaml\n"
            "  - repo: meta\n"
            "  # managed-by-populate-pre-commit end: meta.yaml\n"
        )
        self.assertEqual(content, expected)

    def test_handles_missing_snippet_file(self) -> None:
        self.create_file(".pre-commit-config.yaml", contents="repos:\n")

        with mock.patch.object(
            populate_pre_commit, "SNIPPETS", [("missing.yaml", lambda: True)]
        ):
            populate_pre_commit.populate_pre_commit()

        with open(".pre-commit-config.yaml", "r") as f:
            content = f.read()

        expected = (
            "repos:\n"
            "  # managed-by-populate-pre-commit start: missing.yaml\n"
            "  # managed-by-populate-pre-commit end: missing.yaml\n"
        )
        self.assertEqual(content, expected)


if __name__ == "__main__":
    unittest.main()
