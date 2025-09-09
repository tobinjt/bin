#!/usr/bin/env python3

"""
Runs a command and sends an email if the command fails or produces output.
"""

import argparse
import os as os
import socket as socket
import subprocess as subprocess
import sys
from collections.abc import Sequence


def should_send_mail(
    exit_status: int,
    output: str,
    ignore_exit_status: bool,
    only_on_failure: bool,
) -> bool:
    """
    Determines whether an email should be sent based on command results and flags.

    Args:
        exit_status: The exit status of the command.
        output: The captured output (stdout and stderr) of the command.
        ignore_exit_status: If True, only send mail if output is produced.
        only_on_failure: If True, only send mail if the command fails.

    Returns:
        True if an email should be sent, False otherwise.
    """
    has_output = bool(output)
    has_failed = exit_status != 0

    if only_on_failure:
        return has_failed

    if ignore_exit_status:
        return has_output

    # Default case
    return has_failed or has_output


def main(argv: Sequence[str]) -> int:
    """
    Main function to run a command and send an email on failure or output.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        The exit code of the executed command.
    """
    parser = argparse.ArgumentParser(
        description="Run a command and send an email if it fails or produces output.",
        usage="%(prog)s [OPTIONS] EMAIL_ADDRESS command [args...]",
    )
    parser.add_argument(
        "--ignore_exit_status",
        action="store_true",
        help="Only send mail if output is produced.",
    )
    parser.add_argument(
        "--only_on_failure",
        action="store_true",
        help="Only send mail if the command fails.",
    )
    parser.add_argument("email_address", help="The recipient's email address.")
    parser.add_argument("command", help="The command to run.")
    parser.add_argument(
        "command_args", nargs=argparse.REMAINDER, help="Arguments for the command."
    )

    args = parser.parse_args(argv)
    if args.ignore_exit_status and args.only_on_failure:
        parser.error("Cannot use both --ignore_exit_status and --only_on_failure")

    command_to_run = [args.command] + args.command_args

    result = subprocess.run(
        command_to_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    exit_status = result.returncode
    output = result.stdout

    if should_send_mail(
        exit_status, output, args.ignore_exit_status, args.only_on_failure
    ):
        user = os.getlogin()
        hostname = socket.gethostname()
        subject = f"{user}@{hostname}: {' '.join(command_to_run)}"
        body = f"Exit status: {exit_status}\nOutput:\n{output}"

        subprocess.run(
            ["mail", "-s", subject, args.email_address],
            input=body,
            text=True,
            check=False,
        )

        log_dir = os.path.expanduser("~/tmp/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "send-mail-on-failure-or-output.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{args.email_address} -- {subject}\n")

    return exit_status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
