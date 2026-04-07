#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Golang project."""

import github_workflow_utils


def main() -> None:
    """Parses arguments and generates the workflows."""
    parser = github_workflow_utils.get_parser(
        description="Generate GitHub Actions workflows for a Golang project."
    )
    args = parser.parse_args(namespace=github_workflow_utils.Args())

    workflows = [
        # keep-sorted start
        ("generic_dependabot.template", ".github/dependabot.yml"),
        ("golang_workflow.template", ".github/workflows/golang_pre-commit.yml"),
        # keep-sorted end
    ]

    for template, output_file in workflows:
        content = github_workflow_utils.generate_workflow(
            args.program_name,
            template,
            __file__,
            False,
        )
        github_workflow_utils.write_workflow(output_file, content)


if __name__ == "__main__":
    main()
