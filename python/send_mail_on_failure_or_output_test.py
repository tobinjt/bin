import unittest
from unittest import mock

import send_mail_on_failure_or_output as send_mail


class ShouldSendMailTest(unittest.TestCase):
    """Tests the should_send_mail logic function."""

    def test_default_mode(self) -> None:
        """Tests the default behavior without any flags."""
        self.assertTrue(send_mail.should_send_mail(1, "out", False, False))
        self.assertTrue(send_mail.should_send_mail(1, "", False, False))
        self.assertTrue(send_mail.should_send_mail(0, "out", False, False))
        self.assertFalse(send_mail.should_send_mail(0, "", False, False))

    def test_ignore_exit_status_mode(self) -> None:
        """Tests behavior with --ignore_exit_status."""
        self.assertTrue(send_mail.should_send_mail(1, "out", True, False))
        self.assertFalse(send_mail.should_send_mail(1, "", True, False))
        self.assertTrue(send_mail.should_send_mail(0, "out", True, False))
        self.assertFalse(send_mail.should_send_mail(0, "", True, False))

    def test_only_on_failure_mode(self) -> None:
        """Tests behavior with --only_on_failure."""
        self.assertTrue(send_mail.should_send_mail(1, "out", False, True))
        self.assertTrue(send_mail.should_send_mail(1, "", False, True))
        self.assertFalse(send_mail.should_send_mail(0, "out", False, True))
        self.assertFalse(send_mail.should_send_mail(0, "", False, True))


class MainFunctionTest(unittest.TestCase):
    """Tests the main function of the script."""

    @mock.patch.object(send_mail.os, "getlogin", return_value="testuser")
    @mock.patch.object(send_mail.socket, "gethostname", return_value="testhost")
    @mock.patch.object(send_mail.os.path, "expanduser")
    @mock.patch.object(send_mail.os, "makedirs")
    @mock.patch.object(send_mail, "open", new_callable=mock.mock_open)
    @mock.patch.object(send_mail.subprocess, "run")
    def test_mail_is_sent_on_failure(
        self,
        mock_subprocess_run,
        mock_open,
        mock_makedirs,
        mock_expanduser,
        mock_gethostname,
        mock_getlogin,
    ) -> None:
        """
        Tests that an email is sent when the command fails.
        """
        mock_expanduser.return_value = "/home/testuser/tmp/logs"
        # Mock the command execution
        mock_process_result = mock.create_autospec(
            send_mail.subprocess.CompletedProcess, instance=True
        )
        mock_process_result.returncode = 1
        mock_process_result.stdout = "error output"
        # The first call is the command, the second is the mailer
        mock_subprocess_run.side_effect = [mock_process_result, mock.DEFAULT]

        argv = ["test@example.com", "ls", "nonexistent"]
        exit_code = send_mail.main(argv)

        self.assertEqual(exit_code, 1)
        self.assertEqual(mock_subprocess_run.call_count, 2)

        # Check the command run
        command_call = mock_subprocess_run.call_args_list[0]
        self.assertEqual(command_call.args[0], ["ls", "nonexistent"])

        # Check the mail command
        mail_call = mock_subprocess_run.call_args_list[1]
        expected_subject = "testuser@testhost: ls nonexistent"
        self.assertEqual(
            mail_call.args[0], ["mail", "-s", expected_subject, "test@example.com"]
        )
        self.assertIn("Exit status: 1", mail_call.kwargs["input"])
        self.assertIn("error output", mail_call.kwargs["input"])

        # Check logging
        mock_expanduser.assert_called_once_with("~/tmp/logs")
        mock_makedirs.assert_called_once_with("/home/testuser/tmp/logs", exist_ok=True)
        mock_open.assert_called_once_with(
            "/home/testuser/tmp/logs/send-mail-on-failure-or-output.log",
            "a",
            encoding="utf-8",
        )
        handle = mock_open()
        handle.write.assert_called_once_with(
            f"test@example.com -- {expected_subject}\n"
        )

    @mock.patch.object(send_mail.subprocess, "run")
    def test_mail_is_not_sent_on_success(self, mock_subprocess_run) -> None:
        """
        Tests that no email is sent when the command succeeds with no output.
        """
        mock_process_result = mock.create_autospec(
            send_mail.subprocess.CompletedProcess, instance=True
        )
        mock_process_result.returncode = 0
        mock_process_result.stdout = ""
        mock_subprocess_run.return_value = mock_process_result

        argv = ["test@example.com", "echo", "hello"]
        exit_code = send_mail.main(argv)

        self.assertEqual(exit_code, 0)
        mock_subprocess_run.assert_called_once_with(
            ["echo", "hello"], stdout=mock.ANY, stderr=mock.ANY, text=True
        )


if __name__ == "__main__":
    unittest.main()
