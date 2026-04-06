#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Rust project."""

import github_workflow_utils


def generate_workflow(
    program_name: str, template_name: str, output_shell_completion: bool = False
) -> str:
    """Generates a GitHub Actions workflow from a template.

    Args:
        program_name: The name of the program/binary.
        template_name: The filename of the template to use.
        output_shell_completion: Whether to include steps to generate shell completions.

    Returns:
        The generated YAML content as a string.
    """
    completion_steps = """
          # 1.1 Generate shell completions
          mkdir -p staging/completions
          BIN="target/${{ matrix.platform.target }}/release/${{ matrix.platform.bin }}"

          $BIN --output_shell_completion bash       > staging/completions/{program_name}.bash
          $BIN --output_shell_completion elvish     > staging/completions/{program_name}.elv
          $BIN --output_shell_completion fish       > staging/completions/{program_name}.fish
          $BIN --output_shell_completion powershell > staging/completions/_{program_name}.ps1
          $BIN --output_shell_completion zsh        > staging/completions/_{program_name}
"""
    insertion_point = "cp LICENSE staging/ || true"

    return github_workflow_utils.generate_workflow(
        program_name,
        template_name,
        __file__,
        output_shell_completion,
        completion_steps,
        insertion_point,
    )


def main() -> None:
    """Parses arguments and generates the workflows."""
    parser = github_workflow_utils.get_parser(
        description="Generate GitHub Actions workflows for a Rust project."
    )
    args = parser.parse_args(namespace=github_workflow_utils.Args())

    # 1. Generate and write the release workflow
    release_content = generate_workflow(
        args.program_name,
        "rust_release_workflow.template",
        args.output_shell_completion,
    )
    github_workflow_utils.write_workflow(
        ".github/workflows/release.yml",
        release_content,
    )

    # 2. Generate and write the publish workflow
    publish_content = generate_workflow(
        args.program_name,
        "rust_publish_workflow.template",
        args.output_shell_completion,
    )
    github_workflow_utils.write_workflow(
        ".github/workflows/publish.yml", publish_content
    )

    # 3. Generate and write the dependabot configuration
    dependabot_content = generate_workflow(
        args.program_name,
        "rust_dependabot.template",
        args.output_shell_completion,
    )
    github_workflow_utils.write_workflow(".github/dependabot.yml", dependabot_content)

    # 4. Generate and write the pull request workflow
    pull_request_content = generate_workflow(
        args.program_name,
        "rust_pull_request_workflow.template",
        args.output_shell_completion,
    )
    github_workflow_utils.write_workflow(
        ".github/workflows/pull_request.yml", pull_request_content
    )

    # 5. Generate and write the security audit workflow
    security_audit_content = generate_workflow(
        args.program_name,
        "rust_security_audit.template",
        args.output_shell_completion,
    )
    github_workflow_utils.write_workflow(
        ".github/workflows/security_audit.yml", security_audit_content
    )


if __name__ == "__main__":
    main()
