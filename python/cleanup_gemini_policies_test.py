import os
import tempfile
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import cleanup_gemini_policies


class TestCleanupGeminiPolicies(unittest.TestCase):
    def test_parse_rules(self):
        """Tests that rules are correctly parsed from a TOML file."""
        toml_content = b"""
        [[rule]]
        toolName = "run_shell_command"
        decision = "approve"
        priority = 10
        commandPrefix = ["ls", "cat"]

        [[rule]]
        toolName = "read_file"
        decision = "deny"
        priority = 20
        deny_message = "Reading files is not allowed."
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(toml_content)
            temp_file_name = f.name

        try:
            rules = cleanup_gemini_policies.parse_rules(temp_file_name)
            self.assertEqual(len(rules), 2)
            self.assertEqual(rules[0].toolName, "run_shell_command")
            self.assertEqual(rules[0].decision, "approve")
            self.assertEqual(rules[0].priority, 10)
            self.assertEqual(rules[0].commandPrefix, ["ls", "cat"])
            self.assertIsNone(rules[0].deny_message)

            self.assertEqual(rules[1].toolName, "read_file")
            self.assertEqual(rules[1].decision, "deny")
            self.assertEqual(rules[1].priority, 20)
            self.assertEqual(rules[1].commandPrefix, [])
            self.assertEqual(rules[1].deny_message, "Reading files is not allowed.")
        finally:
            os.remove(temp_file_name)

    def test_process_rules(self):
        """Tests that rules are correctly combined and sorted."""
        rules = [
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="approve",
                priority=10,
                commandPrefix=["ls"],
            ),
            cleanup_gemini_policies.Rule(
                toolName="read_file",
                decision="deny",
                priority=20,
                deny_message="Msg1",
            ),
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="approve",
                priority=10,
                commandPrefix=["cat", "ls"],
            ),
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="deny",
                priority=5,
                commandPrefix=["rm"],
                deny_message="Msg2",
            ),
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="deny",
                priority=5,
                commandPrefix=["shred"],
                deny_message="Msg2",
            ),
        ]

        processed = cleanup_gemini_policies.process_rules(rules)

        self.assertEqual(len(processed), 3)

        # Expected sorting key: (toolName, decision, priority, deny_message)
        # 1. read_file, deny, 20, Msg1
        # 2. run_shell_command, approve, 10, None
        # 3. run_shell_command, deny, 5, Msg2

        self.assertEqual(processed[0].toolName, "read_file")
        self.assertEqual(processed[0].decision, "deny")
        self.assertEqual(processed[0].priority, 20)
        self.assertEqual(processed[0].deny_message, "Msg1")

        self.assertEqual(processed[1].toolName, "run_shell_command")
        self.assertEqual(processed[1].decision, "approve")
        self.assertEqual(processed[1].priority, 10)
        self.assertEqual(
            processed[1].commandPrefix, ["cat", "ls"]
        )  # Combined and sorted
        self.assertIsNone(processed[1].deny_message)

        self.assertEqual(processed[2].toolName, "run_shell_command")
        self.assertEqual(processed[2].decision, "deny")
        self.assertEqual(processed[2].priority, 5)
        self.assertEqual(processed[2].commandPrefix, ["rm", "shred"])
        self.assertEqual(processed[2].deny_message, "Msg2")

    def test_format_rules(self):
        """Tests that rules are formatted into correct TOML strings."""
        rules = [
            cleanup_gemini_policies.Rule(
                toolName="read_file",
                decision="deny",
                priority=20,
                deny_message="Msg1",
            ),
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="approve",
                priority=10,
                commandPrefix=["cat", "ls"],
            ),
        ]

        expected_output = (
            "[[rule]]\n"
            'toolName = "read_file"\n'
            'decision = "deny"\n'
            "priority = 20\n"
            'deny_message = "Msg1"\n'
            "\n"
            "[[rule]]\n"
            'toolName = "run_shell_command"\n'
            'decision = "approve"\n'
            "priority = 10\n"
            "commandPrefix = [\n"
            '    "cat",\n'
            '    "ls",\n'
            "]\n"
        )

        output = cleanup_gemini_policies.format_rules(rules)
        self.assertEqual(output, expected_output)

    @mock.patch.object(cleanup_gemini_policies, "parse_rules")
    @mock.patch.object(cleanup_gemini_policies, "process_rules")
    @mock.patch.object(cleanup_gemini_policies, "format_rules")
    def test_main(
        self, mock_format: mock.Mock, mock_process: mock.Mock, mock_parse: mock.Mock
    ):
        """Tests the main execution function."""
        mock_parse.return_value = []
        mock_process.return_value = []
        mock_format.return_value = "formatted_toml\n"

        with tempfile.NamedTemporaryFile(delete=True) as f:
            temp_file_name = f.name

            with mock.patch("sys.argv", ["cleanup_gemini_policies.py", temp_file_name]):
                cleanup_gemini_policies.main()

            mock_parse.assert_called_once_with(temp_file_name)
            mock_process.assert_called_once_with([])
            mock_format.assert_called_once_with([])

            with open(temp_file_name, "r") as read_handle:
                content = read_handle.read()
            self.assertEqual(content, "formatted_toml\n")


class TestMainIntegration(fake_filesystem_unittest.TestCase):
    @override
    def setUp(self):
        self.setUpPyfakefs()

    def test_main_integration(self):
        """Tests the main execution function end-to-end using pyfakefs."""
        toml_content = """
        [[rule]]
        toolName = "run_shell_command"
        decision = "approve"
        priority = 10
        commandPrefix = ["ls"]

        [[rule]]
        toolName = "read_file"
        decision = "deny"
        priority = 20
        deny_message = "Denied read"

        [[rule]]
        toolName = "run_shell_command"
        decision = "approve"
        priority = 10
        commandPrefix = ["cat"]
        """

        expected_output = (
            "[[rule]]\n"
            'toolName = "read_file"\n'
            'decision = "deny"\n'
            "priority = 20\n"
            'deny_message = "Denied read"\n'
            "\n"
            "[[rule]]\n"
            'toolName = "run_shell_command"\n'
            'decision = "approve"\n'
            "priority = 10\n"
            "commandPrefix = [\n"
            '    "cat",\n'
            '    "ls",\n'
            "]\n"
        )

        file_path = "/fake/dir/policies.toml"
        self.fs.create_file(  # pyright: ignore [reportUnknownMemberType]
            file_path, contents=toml_content.encode("utf-8")
        )
        with mock.patch("sys.argv", ["cleanup_gemini_policies.py", file_path]):
            cleanup_gemini_policies.main()
        with open(file_path, "r", encoding="utf-8") as f:
            actual_output = f.read()
        self.assertEqual(actual_output, expected_output)


if __name__ == "__main__":
    unittest.main()
