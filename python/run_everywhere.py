#!/usr/bin/env python3

"""Executes a command on multiple hosts as different users.

It uses an external `retry` command to handle transient SSH connection issues.

The script also includes a mechanism to wrap its execution with `caffeinate -i`
on macOS to prevent the system from sleeping during its operation. This is
controlled by the `CAFFEINATED` environment variable.
"""

import argparse
import dataclasses
import logging
import os
import shutil
import subprocess
import sys

logger = logging.getLogger("run_everywhere")


# Default mapping of hosts to users.
HOST_USERS: dict[str, list[str]] = {
    "laptop": ["johntobin", "root"],
    "imac": ["johntobin", "root", "arianetobin"],
    "hosting": ["johntobin", "root", "arianetobin"],
    "truenas": ["truenas_admin"],
}


__all__ = [
    "HOST_USERS",
    "Args",
    "Config",
    "HostUserMap",
    "UsageError",
    "main",
    "os",
    "parse_args",
    "run_caffeinated",
    "shutil",
    "subprocess",
    "update_single_host",
]


class UsageError(Exception):
    """Exception raised for invalid usage."""


@dataclasses.dataclass
class HostUserMap:
    """Bi-directional mapping between hosts and users."""

    host_to_users: dict[str, list[str]]
    user_to_hosts: dict[str, list[str]]

    @classmethod
    def from_host_to_users(cls, host_to_users: dict[str, list[str]]) -> "HostUserMap":
        """Creates a HostUserMap from a dictionary mapping hosts to users.

        Args:
            host_to_users: Dictionary mapping host names to lists of user names.

        Returns:
            A HostUserMap instance with host_to_users and user_to_hosts populated.
        """
        user_to_hosts: dict[str, list[str]] = {}
        for host, users in host_to_users.items():
            for user in users:
                user_to_hosts.setdefault(user, []).append(host)
        return cls(host_to_users=host_to_users, user_to_hosts=user_to_hosts)

    def get_all_hosts(self) -> list[str]:
        """Returns all hosts defined in the mapping.

        Returns:
            List of host names.
        """
        return list(self.host_to_users.keys())

    def get_all_users(self) -> list[str]:
        """Returns all users defined in the mapping.

        Returns:
            List of user names.
        """
        return list(self.user_to_hosts.keys())

    def filter_targets(
        self, flag_hosts: list[str], flag_users: list[str]
    ) -> dict[str, list[str]]:
        """Filters target hosts and users based on flag selections.

        A (host, user) pair is enabled if either the host is in flag_hosts
        or the user is in flag_users.

        Args:
            flag_hosts: List of host names specified in flags.
            flag_users: List of user names specified in flags.

        Returns:
            Dictionary mapping enabled host names to lists of enabled user names.
        """
        selected_hosts = set(flag_hosts)
        selected_users = set(flag_users)
        result: dict[str, list[str]] = {}
        for host, users in self.host_to_users.items():
            matched_users = [
                u for u in users if host in selected_hosts or u in selected_users
            ]
            if matched_users:
                result[host] = matched_users
        return result


class Args(argparse.Namespace):
    """Command-line arguments."""

    hosts: str
    users: str
    command: list[str]

    def __init__(
        self,
        hosts: str | None = None,
        users: str | None = None,
        command: list[str] | None = None,
    ) -> None:
        """Initializes Args with default command line argument values.

        Args:
            hosts: Comma-separated list of hosts.
            users: Comma-separated list of users.
            command: Command to execute.
        """
        super().__init__()
        host_map = HostUserMap.from_host_to_users(HOST_USERS)
        default_hosts = ",".join(host_map.get_all_hosts())
        default_users = ",".join(host_map.get_all_users())
        self.hosts = hosts if hosts is not None else default_hosts
        self.users = users if users is not None else default_users
        self.command = list(command) if command is not None else []


@dataclasses.dataclass
class Config:
    """Configuration for running the command."""

    command: list[str]
    hosts: list[str]
    users: list[str]


def parse_args(argv: list[str], host_map: HostUserMap | None = None) -> Config:
    """Parse command line arguments.

    Args:
        argv: Command line arguments.
        host_map: Optional HostUserMap to determine flag defaults.

    Returns:
        The parsed configuration.

    Raises:
        UsageError: If the command is missing.
    """
    map_to_use = host_map or HostUserMap.from_host_to_users(HOST_USERS)
    default_hosts = ",".join(map_to_use.get_all_hosts())
    default_users = ",".join(map_to_use.get_all_users())

    parser = argparse.ArgumentParser(
        description="Executes a command on multiple hosts.",
        epilog=(
            "Use '--' to separate run_everywhere.py options from the command "
            "to be executed, especially if the command has options that might "
            "conflict."
        ),
    )
    parser.add_argument(
        "--hosts",
        default=default_hosts,
        help="A comma-separated list of hosts to run the command on. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--users",
        default=default_users,
        help="A comma-separated list of users to run the command as. Defaults to %(default)s.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="The command to run.")

    args = parser.parse_args(
        argv,
        namespace=Args(hosts=default_hosts, users=default_users),
    )
    config = Config(
        command=args.command,
        hosts=[h.strip() for h in args.hosts.split(",") if h.strip()],
        users=[u.strip() for u in args.users.split(",") if u.strip()],
    )
    if config.command and config.command[0] == "--":
        config.command = config.command[1:]
    if not config.command:
        parser.print_help(file=sys.stderr)
        raise UsageError("No command specified.")
    return config


def update_single_host(host: str, users: list[str], command: list[str]) -> None:
    """Runs a command on a single host as multiple users.

    Args:
        host: The hostname to connect to.
        users: The users to run as.
        command: The command to execute, as a list of strings.
    """
    ssh_targets = {
        "root": f"johntobin@{host}",
    }
    sudo_commands = {
        "root": ["sudo", "--login"],
    }

    for user in users:
        logger.info(f"{user}@{host}")

        ssh_command = (
            []
            if host == "localhost"
            else [
                "ssh",
                "-o",
                "ControlMaster=no",
                "-o",
                "ForwardAgent=yes",
                "-t",
                "-t",
                ssh_targets.get(user, f"{user}@{host}"),
            ]
        )
        full_command = (
            [
                "retry",
            ]
            + ssh_command
            + sudo_commands.get(user, [])
            + command
        )

        logger.info(f"Will run: {full_command}")
        subprocess.run(full_command, check=False)


def main(argv: list[str]) -> int:
    """Main function to parse arguments and run the command on all hosts.

    Args:
        argv: Command-line arguments.

    Returns:
        An exit code, 0 for success.
    """
    try:
        config = parse_args(argv)
    except UsageError:
        return 1

    host_map = HostUserMap.from_host_to_users(HOST_USERS)
    targets = host_map.filter_targets(config.hosts, config.users)

    for host, users in targets.items():
        update_single_host(host, users, config.command)

    return 0


def run_caffeinated(argv: list[str]) -> None:
    """Re-executes the script with `caffeinate -i` if not already caffeinated.

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
