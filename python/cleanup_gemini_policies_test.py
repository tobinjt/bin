import os
import tempfile
import typing
import unittest
from unittest import mock

import pyfakefs.fake_filesystem_unittest

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
        modes = ["default"]

        [[rule]]
        toolName = "read_file"
        decision = "deny"
        priority = 20
        deny_message = "Reading files is not allowed."

        [[rule]]
        toolName = "render_issue"
        mcpName = "Buganizer"
        decision = "allow"
        priority = 950
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            _ = f.write(toml_content)
            temp_file_name = f.name

        try:
            rules = cleanup_gemini_policies.parse_rules(temp_file_name)
            self.assertEqual(len(rules), 3)
            self.assertEqual(rules[0].toolName, "run_shell_command")
            self.assertEqual(rules[0].decision, "approve")
            self.assertEqual(rules[0].priority, 10)
            self.assertEqual(rules[0].commandPrefix, ["ls", "cat"])
            self.assertEqual(rules[0].modes, ["default"])
            self.assertIsNone(rules[0].deny_message)

            self.assertEqual(rules[1].toolName, "read_file")
            self.assertEqual(rules[1].decision, "deny")
            self.assertEqual(rules[1].priority, 20)
            self.assertEqual(rules[1].commandPrefix, [])
            self.assertEqual(rules[1].deny_message, "Reading files is not allowed.")

            self.assertEqual(rules[2].toolName, "render_issue")
            self.assertEqual(rules[2].mcpName, "Buganizer")
            self.assertEqual(rules[2].decision, "allow")
            self.assertEqual(rules[2].priority, 950)
        finally:
            os.remove(temp_file_name)

    def test_parse_rules_unsupported_field(self):
        """Tests that parse_rules reports all unsupported fields across rules."""
        toml_content = b"""
        [[rule]]
        toolName = "run_shell_command"
        decision = "approve"
        priority = 10
        badField1 = "value"
        badField2 = "value"

        [[rule]]
        toolName = "read_file"
        decision = "deny"
        priority = 20
        extraField = "value"
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            _ = f.write(toml_content)
            temp_file_name = f.name

        try:
            with self.assertRaises(ValueError) as cm:
                _ = cleanup_gemini_policies.parse_rules(temp_file_name)

            error_msg = str(cm.exception)
            self.assertIn(
                "Rule 0 has unsupported fields: badField1, badField2", error_msg
            )
            self.assertIn("Rule 1 has unsupported fields: extraField", error_msg)
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
                modes=["default"],
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
                modes=["default"],
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
            cleanup_gemini_policies.Rule(
                toolName="run_shell_command",
                decision="approve",
                priority=10,
                commandPrefix=["grep"],
                modes=["yolo"],
            ),
        ]

        processed = cleanup_gemini_policies.process_rules(rules)

        self.assertEqual(len(processed), 4)

        # Expected sorting key: (toolName, decision, priority, deny_message, modes, mcpName)
        # 1. read_file, deny, 20, Msg1, [], None
        # 2. run_shell_command, approve, 10, None, [default], None
        # 3. run_shell_command, approve, 10, None, [yolo], None
        # 4. run_shell_command, deny, 5, Msg2, [], None

        self.assertEqual(processed[0].toolName, "read_file")
        self.assertEqual(processed[0].decision, "deny")
        self.assertEqual(processed[0].priority, 20)
        self.assertEqual(processed[0].deny_message, "Msg1")

        self.assertEqual(processed[1].toolName, "run_shell_command")
        self.assertEqual(processed[1].decision, "approve")
        self.assertEqual(processed[1].priority, 10)
        self.assertEqual(processed[1].modes, ["default"])
        self.assertEqual(processed[1].commandPrefix, ["cat", "ls"])

        self.assertEqual(processed[2].toolName, "run_shell_command")
        self.assertEqual(processed[2].decision, "approve")
        self.assertEqual(processed[2].priority, 10)
        self.assertEqual(processed[2].modes, ["yolo"])
        self.assertEqual(processed[2].commandPrefix, ["grep"])

        self.assertEqual(processed[3].toolName, "run_shell_command")
        self.assertEqual(processed[3].decision, "deny")
        self.assertEqual(processed[3].priority, 5)
        self.assertEqual(processed[3].commandPrefix, ["rm", "shred"])
        self.assertEqual(processed[3].deny_message, "Msg2")

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
                modes=["default", "yolo"],
            ),
            cleanup_gemini_policies.Rule(
                toolName="render_issue",
                mcpName="Buganizer",
                decision="allow",
                priority=950,
            ),
        ]

        expected_output_default = (
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
            'modes = [ "default", "yolo" ]\n'
            'commandPrefix = [ "cat", "ls" ]\n'
            "\n"
            "[[rule]]\n"
            'toolName = "render_issue"\n'
            'mcpName = "Buganizer"\n'
            'decision = "allow"\n'
            "priority = 950\n"
        )

        output = cleanup_gemini_policies.format_rules(rules)
        self.assertEqual(output, expected_output_default)

        # Test line_length_limit = 20 to trigger wrapping
        # "commandPrefix = [ \"cat\", \"ls\" ]" is 32 chars (> 20)
        expected_output_limit_20 = (
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
            'modes = [ "default", "yolo" ]\n'
            "commandPrefix = [\n"
            '  "cat",\n'
            '  "ls"\n'
            "]\n"
            "\n"
            "[[rule]]\n"
            'toolName = "render_issue"\n'
            'mcpName = "Buganizer"\n'
            'decision = "allow"\n'
            "priority = 950\n"
        )
        output = cleanup_gemini_policies.format_rules(rules, line_length_limit=20)
        self.assertEqual(output, expected_output_limit_20)

    @mock.patch.object(cleanup_gemini_policies, "parse_rules")
    @mock.patch.object(cleanup_gemini_policies, "process_rules")
    @mock.patch.object(cleanup_gemini_policies, "format_rules")
    def test_main(
        self,
        mock_format: mock.Mock,
        mock_process: mock.Mock,
        mock_parse: mock.Mock,
    ):
        """Tests the main execution function."""
        mock_parse.return_value = []
        mock_process.return_value = []
        mock_format.return_value = "formatted_toml\n"

        with tempfile.NamedTemporaryFile(delete=True) as f:
            temp_file_name = f.name

            with mock.patch(
                "sys.argv",
                [
                    "cleanup_gemini_policies.py",
                    temp_file_name,
                    "--line-length-limit",
                    "40",
                ],
            ):
                cleanup_gemini_policies.main()

            mock_parse.assert_called_once_with(temp_file_name)
            mock_process.assert_called_once_with([])
            mock_format.assert_called_once_with([], line_length_limit=40)

            with open(temp_file_name, "r") as read_handle:
                content = read_handle.read()
            self.assertEqual(content, "formatted_toml\n")


class TestMainIntegration(pyfakefs.fake_filesystem_unittest.TestCase):
    @typing.override
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
            'commandPrefix = [ "cat", "ls" ]\n'
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
