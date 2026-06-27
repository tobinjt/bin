#!/usr/bin/env python3
"""Provides a utility to extract host and username from an SSH command line.

It uses `ssh -G` to parse the SSH command line and extract the resolved host and
username.
"""

import dataclasses
import subprocess
import sys


@dataclasses.dataclass(frozen=True)
class SshDetails:
    """Details of the SSH connection extracted from the command line.

    Attributes:
        hostname: The resolved hostname to connect to.
        username: The resolved username to connect with.
    """

    hostname: str
    username: str


def extract_ssh_details(*, ssh_args: list[str]) -> SshDetails:
    """Extracts SSH destination details (hostname and username) using ssh -G.

    Requires that the first element of the arguments is "ssh".

    Args:
        ssh_args: The raw ssh command line arguments.

    Returns:
        An SshDetails object containing the extracted hostname and username.

    Raises:
        ValueError: If hostname or username cannot be parsed from the output.
        subprocess.CalledProcessError: If the ssh -G command fails.
        FileNotFoundError: If the ssh command is not found.
        KeyError: If "user" or "host" is missing from "ssh -G".
    """
    result = subprocess.run(
        ["ssh", "-G"] + ssh_args[1:],
        capture_output=True,
        text=True,
        check=True,
    )

    ssh_config: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            key, val = parts
            ssh_config[key] = val
    return SshDetails(hostname=ssh_config["host"], username=ssh_config["user"])


def main(*, argv: list[str]) -> None:
    """Main function.

    Args:
        argv: Command-line arguments.
    """
    details = extract_ssh_details(ssh_args=argv[1:])
    print(f"{details.username}@{details.hostname}")


if __name__ == "__main__":
    main(argv=sys.argv)
