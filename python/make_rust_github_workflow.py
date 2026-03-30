#!/usr/bin/env python3
"""Script to generate GitHub Actions workflows for a Rust project."""

import argparse
import os


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
    script_dir = os.path.dirname(os.path.realpath(__file__))
    template_path = os.path.join(script_dir, template_name)
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    shebang = f"#!/usr/bin/env -S {os.path.basename(__file__)} {{program_name}}"
    if output_shell_completion:
        shebang += " --output_shell_completion"

    template = shebang + "\n" + template

    if output_shell_completion:
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
        template = template.replace(
            insertion_point, insertion_point + "\n" + completion_steps
        )

    return template.replace("{program_name}", program_name).rstrip()


def write_workflow(output_file: str, content: str) -> None:
    """Writes the workflow content to a file and makes it executable.

    Args:
        output_file: The path to the file to write.
        content: The content to write.
    """
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    os.chmod(output_file, 0o755)


def main() -> None:
    """Parses arguments and generates the workflows."""
    parser = argparse.ArgumentParser(
        description="Generate GitHub Actions workflows for a Rust project."
    )
    parser.add_argument("program_name", help="The name of the program to release.")
    parser.add_argument(
        "output_file",
        nargs="?",
        default=".github/workflows/release.yml",
        help="Output file for the release workflow. Defaults to .github/workflows/release.yml",
    )
    parser.add_argument(
        "--output_shell_completion",
        action="store_true",
        help="Include steps to generate shell completions in the release workflow.",
    )
    args = parser.parse_args()

    # 1. Generate and write the release workflow
    release_content = generate_workflow(
        args.program_name,  # pyright: ignore [reportAny]
        "rust_release_workflow.template",
        args.output_shell_completion,  # pyright: ignore [reportAny]
    )
    write_workflow(
        args.output_file,  # pyright: ignore [reportAny]
        release_content,
    )

    # 2. Generate and write the publish workflow
    publish_content = generate_workflow(
        args.program_name,  # pyright: ignore [reportAny]
        "rust_publish_workflow.template",
        args.output_shell_completion,  # pyright: ignore [reportAny]
    )
    publish_output = os.path.join(
        os.path.dirname(args.output_file),  # pyright: ignore [reportAny]
        "publish.yml",
    )
    write_workflow(publish_output, publish_content)


if __name__ == "__main__":
    main()
