import unittest
from unittest import mock

import io
import logging
import sys
import retry_tool


class RetryMainTest(unittest.TestCase):
    """Tests for the main function of the retry script."""

    @mock.patch.object(retry_tool.subprocess, "run")
    def test_command_succeeds_first_time(self, mock_subprocess_run: mock.Mock) -> None:
        mock_subprocess_run.return_value = mock.create_autospec(
            retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
        )

        argv = ["test message", "true"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        mock_subprocess_run.assert_called_once_with(["true"], check=False)

    @mock.patch.object(retry_tool.subprocess, "run")
    @mock.patch("builtins.input", return_value="")
    def test_command_fails_then_succeeds(
        self,
        mock_input: mock.Mock,
        mock_subprocess_run: mock.Mock,
    ) -> None:
        mock_subprocess_run.side_effect = [
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=1
            ),
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
            ),
        ]

        argv = ["retrying...", "--", "my-command", "--arg"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_subprocess_run.assert_has_calls(
            [mock.call(["my-command", "--arg"], check=False)] * 2
        )
        mock_input.assert_called_once_with("Press Enter to retry: ")

    @mock.patch.object(retry_tool.subprocess, "run")
    @mock.patch("builtins.input", return_value="")
    def test_command_raises_oserror_then_succeeds(
        self,
        mock_input: mock.Mock,
        mock_subprocess_run: mock.Mock,
    ) -> None:
        mock_subprocess_run.side_effect = [
            OSError("Permission denied"),
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
            ),
        ]

        argv = ["retrying...", "--", "my-command"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_input.assert_called_once_with("Press Enter to retry: ")

    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_not_enough_arguments(
        self, mock_stdout: io.StringIO, _unused_mock_exit: mock.Mock
    ) -> None:
        return_code = retry_tool.main(["message"])
        self.assertEqual(return_code, 2)
        # Check that the usage string was printed
        self.assertIn("usage:", mock_stdout.getvalue())

        return_code_no_args = retry_tool.main([])
        self.assertEqual(return_code_no_args, 2)
        # Check that the usage string was printed
        self.assertIn("usage:", mock_stdout.getvalue())

    @mock.patch.object(retry_tool.subprocess, "run")
    @mock.patch.object(logging, "basicConfig")
    def test_quiet_option_suppresses_info(
        self, mock_basic_config: mock.Mock, mock_subprocess_run: mock.Mock
    ) -> None:
        """Test that -q or --quiet option sets logger level to WARNING.

        Args:
            mock_basic_config: Mocked setLevel method.
            mock_subprocess_run: Mocked subprocess.run function.

        Returns:
            None.
        """
        mock_subprocess_run.return_value = mock.create_autospec(
            retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
        )

        argv = ["-q", "test message", "true"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        mock_basic_config.assert_called_once_with(level=logging.WARNING)

    @mock.patch.object(retry_tool.subprocess, "run")
    @mock.patch.object(logging, "basicConfig")
    def test_no_quiet_option_default_level(
        self, mock_basic_config: mock.Mock, mock_subprocess_run: mock.Mock
    ) -> None:
        """Test that without quiet option, logger level is set to NOTSET.

        Args:
            mock_basic_config: Mocked basicConfig method.
            mock_subprocess_run: Mocked subprocess.run function.

        Returns:
            None.
        """
        mock_subprocess_run.return_value = mock.create_autospec(
            retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
        )

        argv = ["test message", "true"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        mock_basic_config.assert_called_once_with(level=logging.INFO)


if __name__ == "__main__":
    unittest.main()
