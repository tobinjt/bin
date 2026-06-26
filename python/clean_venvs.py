#!/usr/bin/env python3
"""Clean up unused Python virtual environments in a directory.

This script recursively deletes all virtualenv directories inside a target
directory, except the one that is currently active (pointed to by a symlink).
"""

import argparse
import pathlib
import shutil
import sys


class Args(argparse.Namespace):
    """Namespace for command-line arguments."""

    directory: str
    dry_run: bool
    verbose: bool
    symlink_name: str

    def __init__(
        self,
        directory: str = "~/tmp/bin/virtualenv/",
        dry_run: bool = False,
        verbose: bool = False,
        symlink_name: str = "Python",
    ) -> None:
        """Initialize the command line arguments.

        Args:
            directory: The virtualenv directory to clean up.
            dry_run: If True, only log the directories that would be deleted.
            verbose: If True, print detailed log messages.
            symlink_name: The name of the symlink pointing to the active venv.
        """
        super().__init__()
        self.directory = directory
        self.dry_run = dry_run
        self.verbose = verbose
        self.symlink_name = symlink_name


def clean_virtualenvs(
    virtualenv_dir: pathlib.Path,
    symlink_name: str,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Clean up unused virtual environments in the specified directory.

    Deletes all directories in `virtualenv_dir` except for the one pointed to
    by the active symlink (and its parent directories relative to the root).

    Args:
        virtualenv_dir: The directory containing virtual environments.
        symlink_name: The name of the symlink pointing to the active venv.
        dry_run: If True, do not perform deletion.
        verbose: If True, print verbose progress.

    Raises:
        FileNotFoundError: If the target directory or symlink does not exist.
    """
    if not virtualenv_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {virtualenv_dir}")

    # Look for the symlink with case-sensitive matching first, then lowercase.
    # This ensures child == symlink_path comparison works correctly.
    dir_symlinks = {p.name: p for p in virtualenv_dir.iterdir() if p.is_symlink()}
    alt_symlink_name = symlink_name.lower()

    if symlink_name in dir_symlinks:
        symlink_path = dir_symlinks[symlink_name]
    elif alt_symlink_name in dir_symlinks:
        symlink_path = dir_symlinks[alt_symlink_name]
    else:
        raise FileNotFoundError(
            f"Active venv symlink not found in {virtualenv_dir} "
            + f"(tried '{symlink_name}' and '{alt_symlink_name}')"
        )

    try:
        active_venv = symlink_path.resolve(strict=True)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Symlink at {symlink_path} points to a non-existent path: {e}"
        ) from e

    if verbose:
        print(f"Active venv resolved to: {active_venv}")

    for child in virtualenv_dir.iterdir():
        # Do not delete the symlink itself
        if child == symlink_path:
            continue

        if child.is_symlink():
            if verbose or dry_run:
                print(
                    f"{'[DRY RUN] Would delete' if dry_run else 'Deleting'}"
                    + f" symlink: {child}"
                )
            if not dry_run:
                child.unlink()
            continue

        if child.is_dir():
            try:
                resolved_child = child.resolve(strict=True)
            except FileNotFoundError:
                # If resolving fails, it might be a broken symlink or directory
                # that was removed/inaccessible. We safely skip it.
                continue

            # Keep if the active venv is this directory or a descendant of it
            is_active = (resolved_child == active_venv) or (
                resolved_child in active_venv.parents
            )

            if is_active:
                if verbose:
                    print(f"Keeping active venv directory: {child}")
                continue

            if verbose or dry_run:
                print(
                    f"{'[DRY RUN] Would delete' if dry_run else 'Deleting'}"
                    + f" directory: {child}"
                )

            if not dry_run:
                shutil.rmtree(child)


def main(argv: list[str]) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Clean up unused virtual environments in a directory.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="~/tmp/bin/virtualenv/",
        help="Directory to clean up (default: ~/tmp/bin/virtualenv/)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Perform a dry run without deleting anything.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output.",
    )
    parser.add_argument(
        "--symlink-name",
        default="Python",
        help="Name of the active venv symlink (default: Python)",
    )

    args = parser.parse_args(argv[1:], namespace=Args())

    # Expand the user home directory if needed
    target_path = pathlib.Path(args.directory).expanduser()

    try:
        clean_virtualenvs(
            virtualenv_dir=target_path,
            symlink_name=args.symlink_name,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
