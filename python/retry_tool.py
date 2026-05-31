#!/usr/bin/env python3

"""
A command-line utility to retry a command until it succeeds.

This script repeatedly executes a given command until it returns a zero exit
code. It requires user interaction (pressing Enter) before each new attempt.
"""

import argparse
import logging
import os
import subprocess as subprocess
import sys
import typing
from collections import abc


class Args(argparse.Namespace):
    """Command-line arguments for retry_tool."""

    message: str
    command_args: list[str]

    def __init__(self, message: str, command_args: list[str]) -> None:
        """
        Initialise the Args class.

        Args:
            message: Message to display between retries.
            command_args: Command and arguments.
        """
        super().__init__()
        self.message = message
        self.command_args = list(command_args)


# Make basedpyright happy about the type that MyLogger inherits from, while also working
# on Python 3.9 for older MacOS versions.
if typing.TYPE_CHECKING:
    # This is only executed by type checkers (like basedpyright)
    _BaseAdapter = logging.LoggerAdapter[logging.Logger]
else:
    # This is what Python 3.9/3.14 actually runs at runtime
    _BaseAdapter = logging.LoggerAdapter  # pyright: ignore[reportUnreachable]


class MyLogger(_BaseAdapter):
    """Customise the logging output, prepending working directory."""

    def process(  # pyright: ignore[reportImplicitOverride]
        self, msg: str, kwargs: abc.MutableMapping[str, typing.Any]
    ) -> tuple[str, abc.MutableMapping[str, typing.Any]]:
        return (f"{os.getcwd()}: {msg}", kwargs)


def main(argv: abc.Sequence[str]) -> int:
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

    args = parser.parse_args(argv, namespace=Args(message="", command_args=[]))
    if not args.command_args:
        parser.print_usage()
        return 2

    logger = MyLogger(logging.getLogger("retry_tool"), extra={})
    while True:
        logger.info(f"Running: {args.command_args}")
        try:
            result = subprocess.run(args.command_args, check=False)
            if result.returncode == 0:
                return 0
            logger.info(f"Exit status: {result.returncode}")
        except OSError as e:
            logger.warning(f"Failed to run command: {e}")

        logger.warning(f"Command failed. Retrying {args.message}")

        input("Press Enter to retry: ")

        logger.info(f"Retrying {args.message}")


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    sys.exit(main(sys.argv[1:]))
