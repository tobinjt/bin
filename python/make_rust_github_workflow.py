#!/usr/bin/env python3
"""Script to generate a GitHub Actions release workflow for a Rust project."""

import argparse
import os


def generate_workflow(program_name: str) -> str:
    """Generates a GitHub Actions workflow for releasing a Rust program.

    Args:
        program_name: The name of the program/binary.

    Returns:
        The generated YAML content as a string.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "rust_release_workflow.template")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    return template.replace("{program_name}", program_name).rstrip()


def main() -> None:
    """Parses arguments and prints the generated workflow."""
    parser = argparse.ArgumentParser(
        description="Generate a GitHub Actions release workflow for a Rust project."
    )
    parser.add_argument("program_name", help="The name of the program to release.")
    args = parser.parse_args()

    print(generate_workflow(args.program_name))  # pyright: ignore [reportAny]


if __name__ == "__main__":
    main()
