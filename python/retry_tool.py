#!/usr/bin/env python3

"""
A command-line utility to retry a command until it succeeds.

This script repeatedly executes a given command until it returns a zero exit
code. It requires user interaction (pressing Enter) before each new attempt.
"""

import argparse
import logging
import subprocess as subprocess
import sys
from collections.abc import Sequence

logger = logging.getLogger("retry_tool")


class Args(argparse.Namespace):
    """Command-line arguments for retry_tool."""

    message: str = ""
    command_args: list[str] = []


def main(argv: Sequence[str]) -> int:
    """
    Main function to parse arguments and execute the retry logic.

    Args:
        argv: Command-line arguments.

    Returns:
        The exit code of the successfully executed command.
    """
    parser = argparse.ArgumentParser(
        description="Retry a command until it succeeds.",
        usage="%(prog)s MESSAGE -- COMMAND [COMMAND_ARGS...]",
    )
    parser.add_argument("message", help="Message to display between retries.")
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Command and arguments.",
    )

    args = parser.parse_args(argv, namespace=Args())
    if not args.command_args:
        parser.print_usage()
        return 2

    while True:
        logger.info(f"Running: {args.command_args}")
        result = subprocess.run(args.command_args, check=False)
        if result.returncode == 0:
            return 0

        logger.info(f"Exit status: {result.returncode}")
        logger.warning(f"Command failed. Retrying {args.message}")

        input("Press Enter to retry: ")

        logger.info(f"Retrying {args.message}")


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    sys.exit(main(sys.argv[1:]))
