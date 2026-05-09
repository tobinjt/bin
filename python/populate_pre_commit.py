#!/usr/bin/env python3
"""Populates .pre-commit-config.yaml with managed snippets.

This script detects the types of files in the current repository and includes
corresponding pre-commit hooks from a central snippets directory. It uses
markers to identify and update managed sections in .pre-commit-config.yaml.
"""

# Prompt that generated this program:
# I extensively use pre-commit.com for my Git repositories. I want to write a
# program to manage my `.pre-commit-config.yaml` files so that maintaining them is
# easier. All of the configs I currently have are in @pre-commit-configs/.
#
# - Please analyse all of those files, extract any piece of config that's used
#   twice or more into @pre-commit-snippets/ for reuse.
# - Please write a Python program named @populate-pre-commit.py that will:
#   - Be run in the root of a Git repo.
#   - Check the files present in the repo to determine which snippets to include
#     in `.pre-commit-config.yaml` from @pre-commit-snippets/
#   - Update `.pre-commit-config.yaml`, replacing snippets the program previously
#     added, adding missing snippets when new files are added to the repo,
#     *without* changing other config in the file, and keeping the output order
#     consistent to minimise diffs between runs.
#   - For the initial migration of an existing `.pre-commit-config.yaml`, it's
#     fine for the program to add config snippets that are effectively duplicates
#     of existing config, I will manually edit the `.pre-commit-config.yaml`
#     before committing it.

import glob
import os

# Path to the directory containing pre-commit snippets.
SNIPPETS_DIR = os.path.expanduser("~/bin/python/pre-commit-snippets")
# The pre-commit configuration file to update.
CONFIG_FILE = ".pre-commit-config.yaml"


def should_include_actionlint() -> bool:
    """Checks if GitHub Actions workflows exist.

    Returns:
        True if any .yaml or .yml files exist in .github/workflows/.
    """
    return bool(
        glob.glob(".github/workflows/*.yaml") or glob.glob(".github/workflows/*.yml")
    )


def should_include_markdownlint() -> bool:
    """Checks if Markdown files exist.

    Returns:
        True if any .md files exist in the repository.
    """
    return bool(glob.glob("**/*.md", recursive=True))


def should_include_shellcheck() -> bool:
    """Checks if Shell scripts exist.

    Returns:
        True if any .sh files exist in the repository.
    """
    return bool(glob.glob("**/*.sh", recursive=True))


def should_include_python() -> bool:
    """Checks if Python files exist.

    Returns:
        True if any .py files exist in the repository.
    """
    return bool(glob.glob("**/*.py", recursive=True))


def should_include_golang() -> bool:
    """Checks if Go files or a go.mod file exist.

    Returns:
        True if any .go files or a go.mod file exist.
    """
    return bool(glob.glob("**/*.go", recursive=True) or os.path.exists("go.mod"))


def should_include_rust() -> bool:
    """Checks if Rust files or a Cargo.toml file exist.

    Returns:
        True if any .rs files or a Cargo.toml file exist.
    """
    return bool(glob.glob("**/*.rs", recursive=True) or os.path.exists("Cargo.toml"))


# Define snippets and their detection logic in the desired output order.
SNIPPETS = (
    # keep-sorted start
    ("conventional-pre-commit.yaml", lambda: True),
    ("keep-sorted.yaml", lambda: True),
    ("local-actionlint.yaml", should_include_actionlint),
    ("local-basedpyright.yaml", should_include_python),
    ("local-black.yaml", should_include_python),
    ("local-markdownlint.yaml", should_include_markdownlint),
    ("local-mypy.yaml", should_include_python),
    ("local-pytest.yaml", should_include_python),
    ("local-shellcheck.yaml", should_include_shellcheck),
    ("local-spellcheck.yaml", lambda: True),
    ("meta.yaml", lambda: True),
    ("pre-commit-golang-coverage-check.yaml", should_include_golang),
    ("pre-commit-golang.yaml", should_include_golang),
    ("pre-commit-golangci-lint.yaml", should_include_golang),
    ("pre-commit-hooks.yaml", lambda: True),
    ("pygrep-hooks.yaml", should_include_python),
    ("rust-pre-commit-checks.yaml", should_include_rust),
    # keep-sorted end
)


def populate_pre_commit() -> None:
    """Updates .pre-commit-config.yaml with detected snippets."""
    lines: list[str] = []
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()
    else:
        lines = ["repos:\n"]

    # Determine which snippets to include.
    to_include: list[str] = []
    for snippet_name, detector in SNIPPETS:
        if detector():
            to_include.append(snippet_name)

    # 1. Remove all existing managed blocks.
    new_lines: list[str] = []
    skip: bool = False
    for line in lines:
        if line.strip().startswith("# managed-by-populate-pre-commit start:"):
            skip = True
            continue
        if line.strip().startswith("# managed-by-populate-pre-commit end:"):
            skip = False
            continue
        if not skip:
            new_lines.append(line)

    # 2. Find where to insert. Ideally immediately after 'repos:'.
    repos_idx: int = -1
    for i, line in enumerate(new_lines):
        if line.strip().startswith("repos:"):
            repos_idx = i
            break

    if repos_idx == -1:
        # If 'repos:' is missing, add it.
        new_lines.append("repos:\n")
        repos_idx = len(new_lines) - 1

    # 3. Prepare snippet lines.
    snippet_lines: list[str] = []
    for snippet_name in to_include:
        snippet_path: str = os.path.join(SNIPPETS_DIR, snippet_name)
        if not os.path.exists(snippet_path):
            print(f"Warning: Snippet {snippet_name} not found at {snippet_path}")
            continue

        with open(snippet_path, "r") as f:
            content: str = f.read()

        snippet_lines.append(
            f"  # managed-by-populate-pre-commit start: {snippet_name}\n"
        )
        # Indent content by 2 spaces.
        for line in content.splitlines():
            if line.strip():
                snippet_lines.append(f"  {line}\n")
            else:
                snippet_lines.append("\n")
        snippet_lines.append(
            f"  # managed-by-populate-pre-commit end: {snippet_name}\n"
        )

    # 4. Insert snippets.
    insert_pos: int = repos_idx + 1
    final_lines: list[str] = (
        new_lines[:insert_pos] + snippet_lines + new_lines[insert_pos:]
    )

    # 5. Write back to file.
    with open(CONFIG_FILE, "w") as f:
        f.writelines(final_lines)

    print(f"Updated {CONFIG_FILE} with {len(to_include)} snippets.")


if __name__ == "__main__":
    populate_pre_commit()
