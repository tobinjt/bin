#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Python project."""

import github_workflow_utils


def main() -> None:
    """Parses arguments and generates the workflows."""
    workflows = [
        # keep-sorted start
        ("dependabot.yml", ".github/dependabot.yml"),
        ("dependabot_validation.yml", ".github/workflows/dependabot_validation.yml"),
        # keep-sorted end
    ]

    github_workflow_utils.run_main(
        description="Generate GitHub Actions workflows for a Python project.",
        workflows=workflows,
        script_file=__file__,
    )


if __name__ == "__main__":
    main()
