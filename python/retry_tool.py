#!/usr/bin/env python3

"""
A command-line utility to retry a command until it succeeds.

This script repeatedly executes a given command until it returns a zero exit
code. It provides options to configure the delay between retries and to
require user interaction (pressing Enter) before each new attempt.
"""

import argparse
import logging
import subprocess as subprocess
import sys
import time as time
from collections.abc import Sequence


logger = logging.getLogger("retry_tool")


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
        usage=(
            "%(prog)s [--press_enter_before_retrying] "
            "SLEEP_TIME MESSAGE -- COMMAND [COMMAND_ARGS...]"
        ),
    )
    parser.add_argument(
        "--press_enter_before_retrying",
        action="store_true",
        help="If set, the user will be prompted to press enter before retrying.",
    )
    parser.add_argument(
        "sleep_time",
        type=int,
        help="Number of seconds to sleep between retries.",
    )
    parser.add_argument("message", help="Message to display between retries.")
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Command and arguments.",
    )

    args = parser.parse_args(argv)
    if not args.command_args:
        parser.print_usage()
        return 2

    while True:
        logger.info(f"Running: {args.command_args}")
        result = subprocess.run(args.command_args, check=False)
        if result.returncode == 0:
            return 0

        logger.info(f"Exit status: {result.returncode}")
        logger.warning(
            f"Sleeping for {args.sleep_time} seconds before retrying {args.message}"
        )
        time.sleep(args.sleep_time)

        if args.press_enter_before_retrying:
            input("Press Enter to retry: ")

        logger.info(f"Retrying {args.message}")


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    sys.exit(main(sys.argv[1:]))
