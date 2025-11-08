#!/usr/bin/env python3

"""
A utility to convert a basic crontab line into a launchd.plist file,
including the current $PATH from the environment.
"""

import argparse
import os as os
import pathlib as pathlib
import plistlib as plistlib
import re
import sys as sys
import textwrap
import dataclasses


def as_dict_factory(data: list[tuple[str, str | int | None]]) -> dict[str, str | int]:
    """Factory for dataclasses.asdict to filter out None values."""
    return {k: v for k, v in data if v is not None}


@dataclasses.dataclass
class StartCalendarInterval:
    """Represents the StartCalendarInterval dictionary in a launchd.plist."""

    Minute: int | None = None
    Hour: int | None = None
    Day: int | None = None
    Month: int | None = None
    Weekday: int | None = None


@dataclasses.dataclass
class LaunchdPlist:
    """Represents the structure of a launchd.plist file.

    Attribute names are chosen to match launchd attribute names.
    """

    Label: str
    ProgramArguments: list[str]
    StartCalendarInterval: StartCalendarInterval
    EnvironmentVariables: dict[str, str] = dataclasses.field(default_factory=dict)
    StandardOutPath: str | None = None
    StandardErrorPath: str | None = None

    def to_dict(self) -> dict[str, str | int]:
        """Converts the dataclass to a dictionary suitable for plistlib."""
        return dataclasses.asdict(self, dict_factory=as_dict_factory)


class Args(argparse.Namespace):
    """Namespace for command-line arguments."""

    crontab_line: str = ""
    label: str = ""
    write: bool = False


def expand_path(path: str) -> pathlib.Path:
    """Expands a path to an absolute path.  Here for mocking."""
    return pathlib.Path(path).expanduser()


def create_plist(crontab_line: str, label: str) -> LaunchdPlist:
    """
    Parses a crontab line and label into a LaunchdPlist object.

    Args:
        crontab_line: A single line from a crontab file.
                      e.g. "30 2 * * * /path/to/your/script.sh"
                      This defines when to run the job and the command to execute.
        label: A unique identifier for the job.
               This is used by launchd to manage the job.
               e.g. "com.example.my-daily-backup"

    Returns:
        A LaunchdPlist object.

    Raises:
        ValueError: If the crontab line is invalid.
    """
    # Parse the line.
    line_to_parse = crontab_line.strip()
    line_to_parse = re.sub(r"^@daily", "0 0 * * *", line_to_parse)
    parts = line_to_parse.split(maxsplit=5)
    if len(parts) != 6:
        raise ValueError(
            "Invalid crontab line. Expected 5 time fields and a command,"
            + f" or an alias like @daily: {crontab_line}"
        )
    minute, hour, day_month, month, day_week, command = parts

    # Build StartCalendarInterval.
    cron_map = {
        "Minute": minute,
        "Hour": hour,
        "Day": day_month,
        "Month": month,
        "Weekday": day_week,
    }
    calendar_interval_values: dict[str, int] = {}
    for key, value in cron_map.items():
        if value == "*":
            # In launchd, omitting a key is the same as a wildcard ('*')
            continue
        try:
            calendar_interval_values[key] = int(value)
        except ValueError as e:
            raise ValueError(
                f"Error: value '{value}' for '{key}' is not a simple integer or '*'."
                + " This script only supports basic cron syntax (e.g., '5' or '*')."
                + " Features like '*/15' or '1-5' are not supported."
            ) from e
    calendar_interval = StartCalendarInterval(**calendar_interval_values)

    log_dir = expand_path("~/tmp/logs/launchd")
    log_dir.mkdir(parents=True, exist_ok=True)
    default_path = expand_path("~/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    path = os.environ.get("PATH") or str(default_path)
    return LaunchdPlist(
        Label=label,
        # We use /bin/sh -c to execute the command, just like cron does.
        # This correctly handles redirects (>, >>), pipes (|), etc.
        ProgramArguments=["/bin/sh", "-c", command],
        StartCalendarInterval=calendar_interval,
        EnvironmentVariables={"PATH": path},
        StandardOutPath=str(log_dir / f"{label}.out"),
        StandardErrorPath=str(log_dir / f"{label}.err"),
    )


def main(argv: list[str]) -> int:
    """Parses command-line arguments and prints the generated plist file."""
    parser = argparse.ArgumentParser(
        description="Convert a basic crontab line to a launchd.plist file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              ./cron_to_plist.py -l com.my.job "* 5 * * * my_script.sh --hourly"
              ./cron_to_plist.py -l com.my.job.daily "@daily my_script.sh --daily"

            This will output a .plist file to standard output.
            Save it and load it like this:
              ./cron_to_plist.py ... > ~/Library/LaunchAgents/com.my.job.plist
              launchctl load ~/Library/LaunchAgents/com.my.job.plist
            """
        ),
    )
    parser.add_argument(
        "crontab_line", help="The full crontab line, enclosed in quotes."
    )
    parser.add_argument(
        "-l",
        "--label",
        required=True,
        help="The Label for the launchd job (e.g., com.myuser.dailyjob)",
    )
    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
        help="Write the plist file to ~/Library/LaunchAgents/.",
    )
    args = parser.parse_args(argv[1:], namespace=Args())

    try:
        plist_obj = create_plist(args.crontab_line, args.label)
        plist_xml = plistlib.dumps(plist_obj.to_dict(), sort_keys=True).decode("utf-8")
    except ValueError as e:
        print(f"Error generating plist XML: {e}", file=sys.stderr)
        return 1

    if args.write:
        launch_agents_dir = expand_path("~/Library/LaunchAgents")
        launch_agents_dir.mkdir(parents=True, exist_ok=True)
        output_path = launch_agents_dir / f"{args.label}.plist"
        with open(output_path, "w") as f:
            f.write(plist_xml)
        print(f"Wrote plist to {output_path}")
    else:
        print(plist_xml.rstrip("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
