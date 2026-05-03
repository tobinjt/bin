"""Utility module for generating GitHub Actions workflows."""

import argparse as argparse
import os
import yaml as yaml
from typing import cast, override, TypeAlias

UpdateStanza: TypeAlias = dict[str, str | dict[str, str] | dict[str, int]]


class IndentDumper(yaml.SafeDumper):
    @override
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        # The magic happens here: we force indentless to be False
        return super(IndentDumper, self).increase_indent(flow, False)


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


def generate_dependabot_config(program_name: str, script_file: str) -> str:
    """Generates the dependabot.yml content based on the project files.

    Args:
        program_name: The name of the program to release.
        script_file: The path to the script calling this function.

    Returns:
        The generated YAML content as a string.
    """
    script_dir = os.path.dirname(os.path.realpath(script_file))
    template_path = os.path.join(script_dir, "dependabot.yml")

    with open(template_path, "r", encoding="utf-8") as f:
        template = cast(dict[str, int | list[UpdateStanza]], yaml.safe_load(f))

    ecosystems = {
        "gomod": ["go.mod"],
        "cargo": ["Cargo.toml"],
        "pip": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
    }

    filtered_updates: list[UpdateStanza] = []
    # cast to object first to appease basedpyright.
    updates = cast(list[UpdateStanza], cast(object, template["updates"]))
    for update in updates:
        ecosystem = cast(str, update["package-ecosystem"])
        if ecosystem == "github-actions":
            filtered_updates.append(update)
            continue

        trigger_files = ecosystems[ecosystem]
        if any(os.path.exists(f) for f in trigger_files):
            filtered_updates.append(update)

    template["updates"] = filtered_updates

    yaml_content = yaml.dump(
        template, Dumper=IndentDumper, sort_keys=False, default_flow_style=False
    )
    # Ensure there is a newline between list items for better readability
    yaml_content = yaml_content.replace("\n  - ", "\n\n  - ")

    shebang = f"#!/usr/bin/env -S {os.path.basename(script_file)} {program_name}"
    return shebang + "\n" + yaml_content.rstrip()


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


def run_main(
    description: str,
    workflows: list[tuple[str, str]],
    script_file: str,
) -> None:
    """Parses arguments and generates the workflows.

    Args:
        description: The description for the argument parser.
        workflows: A list of tuples containing (template_name, output_file_path).
        script_file: The path to the script calling this function.
    """
    parser = get_parser(description=description)
    args = parser.parse_args(namespace=Args())

    # Generate dependabot.yml automatically.
    dependabot_content = generate_dependabot_config(args.program_name, script_file)
    write_workflow(".github/dependabot.yml", dependabot_content)

    for template, output_file in workflows:
        if template == "dependabot.yml":
            continue
        content = generate_workflow(
            args.program_name,
            template,
            script_file,
        )
        write_workflow(output_file, content)
