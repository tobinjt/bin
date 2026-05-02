#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Rust project."""

import os

import github_workflow_utils


def main() -> None:
    """Parses arguments and generates the workflows."""
    parser = github_workflow_utils.get_parser(
        description="Generate GitHub Actions workflows for a Rust project."
    )
    args = parser.parse_args(namespace=github_workflow_utils.Args())

    workflows = [
        # keep-sorted start
        ("dependabot.yml", "dependabot.yml"),
        ("rust_publish.yml", "workflows/rust_publish.yml"),
        ("rust_pull_request.yml", "workflows/rust_pull_request.yml"),
        ("rust_security_audit.yml", "workflows/rust_security_audit.yml"),
        # keep-sorted end
    ]

    for template, output_file in workflows:
        content = github_workflow_utils.generate_workflow(
            args.program_name,
            template,
            script_file=__file__,
        )
        github_workflow_utils.write_workflow(
            os.path.join(".github", output_file), content
        )


if __name__ == "__main__":
    main()
