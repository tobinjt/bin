#!/usr/bin/env python3
"""Populates .pre-commit-config.yaml with managed snippets.

This script detects the types of files in the current repository and includes
corresponding pre-commit hooks from a central snippets directory. It uses
markers to identify and update managed sections in .pre-commit-config.yaml.
"""

import argparse
import glob
import os
import yaml
from typing import cast, TypedDict

# Path to the directory containing pre-commit snippets.
SNIPPETS_DIR = os.path.expanduser("~/bin/python/pre-commit-snippets")
# The pre-commit configuration file to update.
CONFIG_FILE = ".pre-commit-config.yaml"


class Hook(TypedDict):
    """Represents a single hook in a config snippet."""

    id: str
    stages: list[str]
    args: list[str]


class RepoEntry(TypedDict):
    """Represents a single repo entry from a config snippet."""

    repo: str
    rev: str
    hooks: list[Hook]


# A full config snippet.
PreCommitConfig = list[RepoEntry]


class Args(argparse.Namespace):
    """Arguments for the pre-commit population script."""

    ignored_filename: str | None
    extra_args: list[str]

    def __init__(
        self,
        ignored_filename: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        """Initializes the arguments.

        Args:
            ignored_filename: An optional filename that is ignored.
            extra_args: Extra arguments for a hook, in the format 'hook_id=args'.
        """
        super().__init__()
        self.ignored_filename = ignored_filename
        self.extra_args = list(extra_args) if extra_args is not None else []


def escape_for_env_s(text: str) -> str:
    r"""Escapes a string for use within an env -S shebang.

    Replace spaces with \_ for env -S compatibility in shebangs.
    env -S will treat \_ as a space when inside quotes.
    We also need to escape double quotes and backslashes.

    Args:
        text: The string to escape.

    Returns:
        The escaped string.
    """
    return text.replace("\\", "\\\\").replace(" ", r"\_").replace('"', r"\"")


def build_shebang_args(extra_args: dict[str, str]) -> str:
    """Builds the argument string for the shebang.

    Args:
        extra_args: The dictionary of extra arguments.

    Returns:
        The string of extra arguments formatted for the shebang.
    """
    args_str = ""
    for cmd, args in sorted(extra_args.items()):
        escaped_cmd = escape_for_env_s(cmd)
        escaped_args = escape_for_env_s(args)
        args_str += f'\\_--extra-arg\\_"{escaped_cmd}={escaped_args}"'
    return args_str


def apply_extra_args(content: str, extra_args: dict[str, str]) -> str:
    """Appends extra arguments to specific hooks in the snippet content.

    Args:
        content: The YAML content of the snippet.
        extra_args: A dictionary mapping hook IDs to extra argument strings.

    Returns:
        The modified YAML content.
    """
    config_snippet = cast(PreCommitConfig, yaml.safe_load(content))
    for repo in config_snippet:
        for hook in repo["hooks"]:
            hook_id = hook["id"]
            if hook_id in extra_args:
                # Append extra flags so they can override existing flags.
                hook["args"].extend(extra_args[hook_id].split())
    return yaml.dump(config_snippet, sort_keys=False, default_flow_style=False)


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
    ("actionlint.yaml", should_include_actionlint),
    ("basedpyright.yaml", should_include_python),
    ("black.yaml", should_include_python),
    ("conventional-pre-commit.yaml", lambda: True),
    ("golang-coverage-check.yaml", should_include_golang),
    ("golang.yaml", should_include_golang),
    ("golangci-lint.yaml", should_include_golang),
    ("hooks.yaml", lambda: True),
    ("keep-sorted.yaml", lambda: True),
    ("markdownlint.yaml", should_include_markdownlint),
    ("meta.yaml", lambda: True),
    ("mypy.yaml", should_include_python),
    ("pygrep-hooks.yaml", should_include_python),
    ("pytest.yaml", should_include_python),
    ("rust.yaml", should_include_rust),
    ("shellcheck.yaml", should_include_shellcheck),
    ("spellcheck.yaml", lambda: True),
    # keep-sorted end
)


def populate_pre_commit(*, extra_args: dict[str, str], script_file: str) -> None:
    """Updates .pre-commit-config.yaml with detected snippets.

    Args:
        extra_args: A dictionary mapping hook IDs to extra arguments.
        script_file: The path to the script calling this function (used for shebang).
    """
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

    # 1. Remove all existing managed blocks AND the shebang.
    new_lines: list[str] = []
    skip: bool = False
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("#!"):
            continue
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
        with open(snippet_path, "r") as f:
            content: str = f.read()
        if not content.strip():
            raise ValueError(f"config snippet {snippet_path} is empty")

        snippet_lines.append(
            f"  # managed-by-populate-pre-commit start: {snippet_name}\n"
        )
        snippet_content = apply_extra_args(content, extra_args)
        for line in snippet_content.splitlines():
            snippet_lines.append(f"  {line}\n")
        snippet_lines.append(
            f"  # managed-by-populate-pre-commit end: {snippet_name}\n"
        )

    # 4. Insert snippets.
    insert_pos: int = repos_idx + 1
    final_lines: list[str] = (
        new_lines[:insert_pos] + snippet_lines + new_lines[insert_pos:]
    )

    # 5. Write back to file with shebang.
    shebang_args = build_shebang_args(extra_args)
    script_name = escape_for_env_s(os.path.basename(script_file))
    shebang = f'#!/usr/bin/env -S "{script_name}"{shebang_args}\n'

    with open(CONFIG_FILE, "w") as f:
        f.write(shebang)
        f.writelines(final_lines)
    os.chmod(CONFIG_FILE, 0o755)

    print(f"Updated {CONFIG_FILE} with {len(to_include)} snippets.")


def main() -> None:
    """Parses arguments and populates the pre-commit config."""
    parser = argparse.ArgumentParser(
        description="Populate .pre-commit-config.yaml with managed snippets."
    )
    parser.add_argument(
        "ignored_filename",
        nargs="?",
        help="An optional filename that is ignored (used when invoked via shebang).",
    )
    parser.add_argument(
        "--extra-arg",
        dest="extra_args",
        action="append",
        help="Extra arguments for a hook, in the format 'hook_id=args'.",
    )
    args = parser.parse_args(namespace=Args())

    command_to_extra_args: dict[str, str] = {}
    for item in args.extra_args:
        if "=" not in item:
            raise ValueError(
                f"Invalid --extra-arg format: '{item}'. Expected 'hook_id=args'."
            )
        hook_id, extra = item.split("=", 1)
        command_to_extra_args[hook_id.strip()] = extra.strip()

    populate_pre_commit(extra_args=command_to_extra_args, script_file=__file__)


if __name__ == "__main__":
    main()
