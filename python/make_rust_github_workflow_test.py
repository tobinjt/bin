import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import make_rust_github_workflow


class TestMakeGithubWorkflow(unittest.TestCase):
    def test_generate_workflow(self) -> None:
        """Tests that the workflow generation produces expected content."""
        program_name = "testapp"
        content = make_rust_github_workflow.generate_workflow(program_name)

        # Check for key sections and program name replacement
        self.assertIn("name: Release", content)
        self.assertIn(f"bin: {program_name}", content)
        self.assertIn(f"name: {program_name}-linux-x86_64.tar.gz", content)
        self.assertIn(f"name: {program_name}-macos-x86_64.tar.gz", content)
        self.assertIn(f"name: {program_name}-macos-arm64.tar.gz", content)

        # Check for the bash parameter expansion line
        # It should look like: VERSIONED_NAME="${VERSIONED_NAME/testapp-/testapp-${{ github.ref_name }}-}"
        expected_line = (
            f'VERSIONED_NAME="${{VERSIONED_NAME/{program_name}-/'
            f'{program_name}-${{{{ github.ref_name }}}}-}}"'
        )
        self.assertIn(expected_line, content)

    @mock.patch.object(sys, "argv", ["make_rust_github_workflow.py", "cliapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly prints generated workflow."""
        with io.StringIO() as buf, redirect_stdout(buf):
            make_rust_github_workflow.main()
            output = buf.getvalue()
            self.assertIn("name: Release", output)
            self.assertIn("bin: cliapp", output)


if __name__ == "__main__":
    unittest.main()
