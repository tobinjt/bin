"""Utility module for generating GitHub Actions workflows."""

import argparse
import os


class Args(argparse.Namespace):
    """Arguments for the workflow generation scripts."""

    program_name: str
    ignored_filename: str | None

    def __init__(
        self,
        program_name: str = "",
        ignored_filename: str | None = None,
    ) -> None:
        """Initializes the arguments.

        Args:
            program_name: The name of the program to release.
            ignored_filename: An optional filename that is ignored.
        """
        super().__init__()
        self.program_name = program_name
        self.ignored_filename = ignored_filename


def generate_workflow(
    program_name: str,
    template_name: str,
    script_file: str,
) -> str:
    """Generates a GitHub Actions workflow from a template.

    Args:
        program_name: The name of the program/binary.
        template_name: The filename of the template to use.
        script_file: The path to the script calling this function (used for shebang and template location).

    Returns:
        The generated YAML content as a string.
    """
    script_dir = os.path.dirname(os.path.realpath(script_file))
    template_path = os.path.join(script_dir, template_name)
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    shebang = f"#!/usr/bin/env -S {os.path.basename(script_file)} PROGRAM_NAME"

    template = shebang + "\n" + template

    return template.replace("PROGRAM_NAME", program_name).rstrip()


def write_workflow(output_file: str, content: str) -> None:
    """Writes the workflow content to a file and makes it executable.

    Args:
        output_file: The path to the file to write.
        content: The content to write.
    """
    output_dir = os.path.dirname(output_file)
    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    os.chmod(output_file, 0o755)


def get_parser(description: str) -> argparse.ArgumentParser:
    """Returns a standard argument parser for workflow generation.

    Args:
        description: The description for the argument parser.

    Returns:
        The configured ArgumentParser object.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("program_name", help="The name of the program to release.")
    parser.add_argument(
        "ignored_filename",
        nargs="?",
        help="An optional filename that is ignored (used when invoked via shebang).",
    )
    return parser
