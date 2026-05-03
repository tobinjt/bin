#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Rust project."""

import github_workflow_utils


def main() -> None:
    """Parses arguments and generates the workflows."""
    workflows = [
        # keep-sorted start
        ("dependabot.yml", ".github/dependabot.yml"),
        ("dependabot_validation.yml", ".github/workflows/dependabot_validation.yml"),
        ("rust_publish.yml", ".github/workflows/rust_publish.yml"),
        ("rust_pull_request.yml", ".github/workflows/rust_pull_request.yml"),
        ("rust_security_audit.yml", ".github/workflows/rust_security_audit.yml"),
        # keep-sorted end
    ]

    github_workflow_utils.run_main(
        description="Generate GitHub Actions workflows for a Rust project.",
        workflows=workflows,
        script_file=__file__,
    )


if __name__ == "__main__":
    main()
