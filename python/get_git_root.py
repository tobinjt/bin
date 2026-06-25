"""Provides a utility to find the git repository root directory."""

import subprocess


def get_git_root() -> str:
    """Finds the root of the git repository.

    Returns:
        The absolute path to the root of the git repository.

    Raises:
        subprocess.CalledProcessError: If the git command fails.
        FileNotFoundError: If the git command is not found.
    """
    ret = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return ret.stdout.strip()
