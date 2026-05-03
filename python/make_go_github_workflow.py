#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Golang project."""

import github_workflow_utils


def main() -> None:
    """Parses arguments and generates the workflows."""
    workflows = [
        # keep-sorted start
        ("dependabot_validation.yml", ".github/workflows/dependabot_validation.yml"),
        ("golang_pre-commit.yml", ".github/workflows/golang_pre-commit.yml"),
        # keep-sorted end
    ]

    github_workflow_utils.run_main(
        description="Generate GitHub Actions workflows for a Golang project.",
        workflows=workflows,
        script_file=__file__,
    )


if __name__ == "__main__":
    main()
