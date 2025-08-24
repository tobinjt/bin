#!/usr/bin/env python3

"""
Executes a command on multiple hosts as different users.

It uses an external `retry` command to handle transient SSH connection issues.

The script also includes a mechanism to wrap its execution with `caffeinate -i`
on macOS to prevent the system from sleeping during its operation. This is
controlled by the `CAFFEINATED` environment variable.
"""

import logging
import os
import shutil
import subprocess
import sys


logger = logging.getLogger("run_everywhere")


def update_single_host(host: str, command: list[str]) -> None:
    """
    Runs a command on a single host as multiple users.

    Args:
        host: The hostname to connect to.
        command: The command to execute, as a list of strings.
    """
    users = {
        "johntobin": f"johntobin@{host}",
        "root": f"johntobin@{host}",
        "arianetobin": f"arianetobin@{host}",
    }

    for user, ssh_target in users.items():
        logger.info(f"{user}@{host}")

        ssh_command_base = ["ssh", "-o", "ControlMaster=no", "-t", ssh_target]

        if user == "root":
            full_command = ssh_command_base + ["sudo", "--login"] + command
        else:
            full_command = ssh_command_base + command

        retry_command = [
            "retry",
            "--press_enter_before_retrying",
            "10",
            f"{user}@{host}",
        ] + full_command

        logger.info(f"Will run: {retry_command}")
        subprocess.run(retry_command, check=False)


def main(argv: list[str]) -> int:
    """
    Main function to parse arguments and run the command on all hosts.

    Args:
        argv: Command-line arguments.

    Returns:
        An exit code, 0 for success.
    """
    if len(argv) < 1:
        print(f"Usage: {sys.argv[0]} COMMAND [ARGS...]", file=sys.stderr)
        return 1

    hosts = ["laptop", "imac", "hosting"]

    for host in hosts:
        update_single_host(host, argv)

    return 0


def run_caffeinated(argv: list[str]) -> None:
    """
    Re-executes the script with `caffeinate -i` if not already caffeinated.

    Args:
        argv: Command-line arguments, including this program.
    """
    if os.environ.get("CAFFEINATED"):
        return

    caffeinate_path = shutil.which("caffeinate")
    if not caffeinate_path:
        # Not on macOS or caffeinate is not installed, proceed without it.
        return

    os.environ["CAFFEINATED"] = "do not sleep"
    args = [caffeinate_path, "-i"] + argv
    os.execvp(args[0], args)


if __name__ == "__main__":
    run_caffeinated(sys.argv)
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    sys.exit(main(sys.argv[1:]))
