#!/usr/bin/env python3
"""Tool for generating GitHub Actions workflows."""

import os
import sys

# Ensure execution inside project .venv if present
_VENV_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ".venv"
)
_VENV_PYTHON = os.path.join(_VENV_DIR, "bin", "python")
if os.path.exists(_VENV_PYTHON) and os.path.abspath(sys.prefix) != os.path.abspath(
    _VENV_DIR
):
    os.execv(_VENV_PYTHON, [_VENV_PYTHON] + sys.argv)

import argparse
import dataclasses
import pathlib
import re
import subprocess
from typing import TypeAlias, cast, override

import get_git_root
import yaml

__all__ = [
    "DEPENDABOT_VALIDATION_WORKFLOW",
    "HUGO_WORKFLOW",
    "LANGUAGE_CONFIGS",
    "Args",
    "IndentDumper",
    "LanguageConfig",
    "UpdateStanza",
    "Workflow",
    "argparse",
    "build_shebang_args",
    "check_hugo_johntobin_ie",
    "copy_actionlint",
    "copy_zizmor",
    "escape_for_env_s",
    "generate_dependabot_config",
    "generate_workflow",
    "get_all_workflows",
    "get_parser",
    "main",
    "remove_workflow",
    "subprocess",
    "write_workflow",
    "yaml",
]

UpdateStanza: TypeAlias = dict[str, str | dict[str, str] | dict[str, int]]


@dataclasses.dataclass(frozen=True, order=True)
class Workflow:
    """A GitHub Actions workflow."""

    template: str
    output: str


@dataclasses.dataclass(frozen=True)
class LanguageConfig:
    """Configuration for a specific language ecosystem."""

    ecosystem: str
    trigger_files: list[str]
    workflows: list[Workflow]


DEPENDABOT_VALIDATION_WORKFLOW = Workflow(
    "dependabot_validation.yml",
    ".github/workflows/dependabot_validation.yml",
)

HUGO_WORKFLOW = Workflow(
    "hugo-johntobin.ie.yml",
    ".github/workflows/hugo-johntobin.ie.yml",
)


LANGUAGE_CONFIGS = [
    LanguageConfig(
        ecosystem="gomod",
        trigger_files=["go.mod"],
        workflows=[
            Workflow(
                "golang_pre-commit.yml", ".github/workflows/golang_pre-commit.yml"
            ),
        ],
    ),
    LanguageConfig(
        ecosystem="cargo",
        trigger_files=["Cargo.toml"],
        workflows=[
            Workflow(
                "rust_pull_request.yml", ".github/workflows/rust_pull_request.yml"
            ),
            Workflow(
                "rust_security_audit.yml", ".github/workflows/rust_security_audit.yml"
            ),
        ],
    ),
    LanguageConfig(
        ecosystem="pip",
        trigger_files=[
            # keep-sorted start
            "Pipfile",
            "pyproject.toml",
            "pyrefly.toml",
            "pytest.ini",
            "python",
            "requirements.txt",
            "setup.py",
            # keep-sorted end
        ],
        workflows=[
            Workflow(
                "python_pre-commit.yml",
                ".github/workflows/python_pre-commit.yml",
            ),
        ],
    ),
    LanguageConfig(
        ecosystem="composer",
        trigger_files=["composer.json"],
        workflows=[],
    ),
    LanguageConfig(
        ecosystem="npm",
        trigger_files=["package.json"],
        workflows=[],
    ),
]


class IndentDumper(yaml.SafeDumper):
    @override
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        """Forces indentless to be False so list items are indented.

        Args:
            flow: Whether flow style is used.
            indentless: Whether indentless is used (overridden to False).

        Returns:
            The result of the parent class increase_indent call.
        """
        return super().increase_indent(flow, False)


class Args(argparse.Namespace):
    """Arguments for the workflow generation scripts."""

    ignored_filename: str | None
    extra_args: list[str] | None

    def __init__(
        self,
        ignored_filename: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        """Initializes the arguments.

        Args:
            ignored_filename: An optional filename that is ignored.
            extra_args: Extra arguments for a command, in the format 'command=args'.
        """
        super().__init__()
        self.ignored_filename = ignored_filename
        self.extra_args = list(extra_args) if extra_args is not None else []


def escape_for_env_s(text: str) -> str:
    r"""Escapes a string for use within an env -S shebang.

    Replace spaces with \_ for env -S compatibility in shebangs.
    env -S will treat \_ as a space when inside quotes.
    We also need to escape double quotes and backslashes.

    Args:
        text: The string to escape.

    Returns:
        The escaped string.
    """
    return text.replace("\\", "\\\\").replace(" ", r"\_").replace('"', r"\"")


def build_shebang_args(extra_args: dict[str, str] | None) -> str:
    """Builds the argument string for the shebang.

    Args:
        extra_args: The dictionary of extra arguments.

    Returns:
        The string of extra arguments formatted for the shebang.
    """
    if not extra_args:
        return ""

    args_str = ""
    for cmd, args in sorted(extra_args.items()):
        escaped_cmd = escape_for_env_s(cmd)
        escaped_args = escape_for_env_s(args)
        args_str += f'\\_--extra-arg\\_"{escaped_cmd}={escaped_args}"'
    return args_str


def generate_dependabot_config(
    script_file: str,
    extra_args: dict[str, str] | None = None,
) -> str:
    """Generates the dependabot.yml content based on the project files.

    Args:
        script_file: The path to the script calling this function.
        extra_args: An optional dictionary mapping commands to extra arguments.

    Returns:
        The generated YAML content as a string.
    """
    script_dir = pathlib.Path(script_file).resolve().parent
    template_path = script_dir / "workflows" / "dependabot.yml"

    with template_path.open("r", encoding="utf-8") as f:
        template = cast(dict[str, int | list[UpdateStanza]], yaml.safe_load(f))

    filtered_updates: list[UpdateStanza] = []
    # cast to object first to appease basedpyright.
    updates = cast(list[UpdateStanza], cast(object, template["updates"]))
    for update in updates:
        ecosystem = cast(str, update["package-ecosystem"])
        if ecosystem in ("github-actions", "pre-commit"):
            filtered_updates.append(update)
            continue

        config = next((c for c in LANGUAGE_CONFIGS if c.ecosystem == ecosystem), None)
        if config and any(pathlib.Path(f).exists() for f in config.trigger_files):
            filtered_updates.append(update)

    template["updates"] = filtered_updates
    yaml_content = yaml.dump(
        template, Dumper=IndentDumper, sort_keys=False, default_flow_style=False
    )
    # Ensure there is a newline between list items for better readability
    yaml_content = yaml_content.replace("\n  - ", "\n\n  - ")

    shebang_args = build_shebang_args(extra_args)
    script_name = escape_for_env_s(pathlib.Path(script_file).name)
    shebang = f'#!/usr/bin/env -S "{script_name}"{shebang_args}'
    return shebang + "\n" + yaml_content.rstrip()


def generate_workflow(
    template_name: str,
    script_file: str,
    extra_args: dict[str, str] | None = None,
) -> str:
    """Generates a GitHub Actions workflow from a template.

    Args:
        template_name: The filename of the template to use.
        script_file: The path to the script calling this function (used for shebang and template location).
        extra_args: An optional dictionary mapping commands to extra arguments to append.

    Returns:
        The generated YAML content as a string.
    """
    script_dir = pathlib.Path(script_file).resolve().parent
    template_path = script_dir / "workflows" / template_name
    template = template_path.read_text(encoding="utf-8")

    if extra_args:
        for command, extra in extra_args.items():
            # Match 'run: <command>' (possibly with spaces) and append extra args.
            # We use regex to ensure we only replace in 'run:' lines.
            pattern = re.compile(
                rf"^(\s*run:\s*{re.escape(command)})(\s*)$", re.MULTILINE
            )
            template = pattern.sub(rf"\1 {extra}\2", template)

    shebang_args = build_shebang_args(extra_args)
    script_name = escape_for_env_s(pathlib.Path(script_file).name)
    shebang = f'#!/usr/bin/env -S "{script_name}"{shebang_args}'

    return shebang + "\n" + template.rstrip()


def write_workflow(output_file: str, content: str) -> None:
    """Writes the workflow content to a file and makes it executable.

    Args:
        output_file: The path to the file to write.
        content: The content to write.
    """
    path = pathlib.Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
    path.chmod(0o755)


def remove_workflow(output_file: str) -> None:
    """Removes a workflow file from the destination if it exists.

    Args:
        output_file: The path to the file to remove.

    Raises:
        subprocess.CalledProcessError: If git rm fails.
    """
    path = pathlib.Path(output_file)
    if path.exists():
        subprocess.run(["git", "rm", output_file], check=True)


def get_parser(description: str) -> argparse.ArgumentParser:
    """Returns a standard argument parser for workflow generation.

    Args:
        description: The description for the argument parser.

    Returns:
        The configured ArgumentParser object.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "ignored_filename",
        nargs="?",
        help="An optional filename that is ignored (used when invoked via shebang).",
    )
    parser.add_argument(
        "--extra-arg",
        dest="extra_args",
        action="append",
        help="Extra arguments for a command, in the format 'command=args' (e.g. --extra-arg 'cargo test=-- --nocapture').",
    )
    return parser


def check_hugo_johntobin_ie() -> bool:
    """Checks if config.toml exists and contains the baseURL line.

    Returns:
        True if config.toml exists and contains the baseURL line,
        False otherwise.
    """
    config_path = pathlib.Path("config.toml")
    if not config_path.exists():
        return False
    try:
        with config_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == 'baseURL = "https://www.johntobin.ie/"':
                    return True
    except OSError:
        return False
    return False


def copy_zizmor(script_file: str) -> None:
    """Copies zizmor.yaml unconditionally to the destination.

    Args:
        script_file: The path to the script calling this function.

    Returns:
        None.

    Raises:
        OSError: If reading the source file or writing the destination file fails.
    """
    script_dir = pathlib.Path(script_file).resolve().parent
    zizmor_source = script_dir / "zizmor.yaml"
    zizmor_dest = pathlib.Path(".github/zizmor.yaml")
    zizmor_dest.parent.mkdir(parents=True, exist_ok=True)
    zizmor_dest.write_text(zizmor_source.read_text(encoding="utf-8"), encoding="utf-8")


def copy_actionlint(script_file: str) -> None:
    """Copies actionlint.yaml unconditionally to the destination.

    Args:
        script_file: The path to the script calling this function.

    Returns:
        None.

    Raises:
        OSError: If reading the source file or writing the destination file fails.
    """
    script_dir = pathlib.Path(script_file).resolve().parent
    actionlint_source = script_dir / "workflows" / "actionlint.yaml"
    actionlint_dest = pathlib.Path(".github/actionlint.yaml")
    actionlint_dest.parent.mkdir(parents=True, exist_ok=True)
    actionlint_dest.write_text(
        actionlint_source.read_text(encoding="utf-8"), encoding="utf-8"
    )


def get_all_workflows() -> set[Workflow]:
    """Returns all known workflows across all configurations.

    Returns:
        A set of all known Workflow objects.
    """
    workflows = {
        workflow for config in LANGUAGE_CONFIGS for workflow in config.workflows
    }
    workflows.add(DEPENDABOT_VALIDATION_WORKFLOW)
    workflows.add(HUGO_WORKFLOW)
    return workflows


def main() -> None:
    """Parses arguments and generates the workflows.

    Raises:
        ValueError: If an extra argument is not formatted as 'command=args'.
        subprocess.CalledProcessError: If git rm fails.
    """
    description = "Generate GitHub Actions workflows for a project."
    parser = get_parser(description=description)
    args = parser.parse_args(namespace=Args())

    command_to_extra_args: dict[str, str] = {}
    for item in args.extra_args or []:
        if "=" not in item:
            raise ValueError(
                f"Invalid --extra-arg format: '{item}'. Expected 'command=args'."
            )
        command, extra = item.split("=", 1)
        command_to_extra_args[command.strip()] = extra.strip()

    script_file = str(pathlib.Path(__file__).absolute())
    git_root = get_git_root.get_git_root()
    os.chdir(git_root)

    # Generate dependabot.yml automatically.
    dependabot_content = generate_dependabot_config(
        script_file,
        extra_args=command_to_extra_args,
    )
    write_workflow(".github/dependabot.yml", dependabot_content)

    # Copy zizmor.yaml unconditionally to the destination.
    copy_zizmor(script_file)

    # Copy actionlint.yaml unconditionally to the destination.
    copy_actionlint(script_file)

    workflows_to_generate: set[Workflow] = {DEPENDABOT_VALIDATION_WORKFLOW}
    for config in LANGUAGE_CONFIGS:
        if any(pathlib.Path(f).exists() for f in config.trigger_files):
            for workflow in config.workflows:
                workflows_to_generate.add(workflow)

    if check_hugo_johntobin_ie():
        workflows_to_generate.add(HUGO_WORKFLOW)

    workflows_to_remove = get_all_workflows() - workflows_to_generate
    for workflow in sorted(workflows_to_remove):
        remove_workflow(workflow.output)

    for workflow in sorted(workflows_to_generate):
        content = generate_workflow(
            workflow.template,
            script_file,
            extra_args=command_to_extra_args,
        )
        write_workflow(workflow.output, content)


if __name__ == "__main__":
    main()
