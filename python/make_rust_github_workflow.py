#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Rust project."""

import os

import github_workflow_utils


def generate_workflow(program_name: str, template_name: str) -> str:
    """Generates a GitHub Actions workflow from a template.

    Args:
        program_name: The name of the program/binary.
        template_name: The filename of the template to use.

    Returns:
        The generated YAML content as a string.
    """
    return github_workflow_utils.generate_workflow(
        program_name,
        template_name,
        __file__,
    )


def main() -> None:
    """Parses arguments and generates the workflows."""
    parser = github_workflow_utils.get_parser(
        description="Generate GitHub Actions workflows for a Rust project."
    )
    args = parser.parse_args(namespace=github_workflow_utils.Args())

    workflows = [
        # keep-sorted start
        ("dependabot.yml", "dependabot.yml"),
        ("rust_publish_workflow.yml", "workflows/rust_publish.yml"),
        ("rust_pull_request_workflow.yml", "workflows/rust_pull_request.yml"),
        ("rust_security_audit.yml", "workflows/rust_security_audit.yml"),
        # keep-sorted end
    ]

    for template, output_file in workflows:
        content = generate_workflow(
            args.program_name,
            template,
        )
        github_workflow_utils.write_workflow(
            os.path.join(".github", output_file), content
        )


if __name__ == "__main__":
    main()
