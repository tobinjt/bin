import unittest
from unittest import mock

import io
import sys
import retry_tool


class RetryMainTest(unittest.TestCase):
    """Tests for the main function of the retry script."""

    @mock.patch.object(retry_tool.time, "sleep")
    @mock.patch.object(retry_tool.subprocess, "run")
    def test_command_succeeds_first_time(
        self, mock_subprocess_run: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        mock_subprocess_run.return_value = mock.create_autospec(
            retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
        )

        argv = ["5", "test message", "true"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        mock_subprocess_run.assert_called_once_with(["true"], check=False)
        mock_sleep.assert_not_called()

    @mock.patch.object(retry_tool.time, "sleep")
    @mock.patch.object(retry_tool.subprocess, "run")
    def test_command_fails_then_succeeds(
        self, mock_subprocess_run: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        mock_subprocess_run.side_effect = [
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=1
            ),
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
            ),
        ]

        argv = ["3", "retrying...", "--", "my-command", "--arg"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_subprocess_run.assert_has_calls(
            [mock.call(["my-command", "--arg"], check=False)] * 2
        )
        mock_sleep.assert_called_once_with(3)

    @mock.patch.object(retry_tool.time, "sleep")
    @mock.patch.object(retry_tool.subprocess, "run")
    @mock.patch("builtins.input", return_value="")
    def test_press_enter_before_retrying(
        self,
        mock_input: mock.Mock,
        mock_subprocess_run: mock.Mock,
        mock_sleep: mock.Mock,
    ) -> None:
        mock_subprocess_run.side_effect = [
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=1
            ),
            mock.create_autospec(
                retry_tool.subprocess.CompletedProcess, instance=True, returncode=0
            ),
        ]

        argv = ["--press_enter_before_retrying", "1", "msg", "cmd"]
        return_code = retry_tool.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        mock_input.assert_called_once_with("Press Enter to retry: ")

    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=io.StringIO)
    def test_not_enough_arguments(
        self, mock_stdout: io.StringIO, _unused_mock_exit: mock.Mock
    ) -> None:
        return_code = retry_tool.main(["1", "message"])
        self.assertEqual(return_code, 2)
        # Check that the usage string was printed
        self.assertIn("usage:", mock_stdout.getvalue())

        return_code_no_args = retry_tool.main([])
        self.assertEqual(return_code_no_args, 2)
        # Check that the usage string was printed
        self.assertIn("usage:", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
