import unittest
from unittest import mock

import run_everywhere


class RunEverywhereTest(unittest.TestCase):
    """Tests for the run_everywhere script."""

    @mock.patch.object(run_everywhere.subprocess, "run")
    def test_update_single_host(self, mock_subprocess_run: mock.Mock) -> None:
        """
        Tests that the correct SSH commands are constructed and run for a single host.
        """
        host = "testhost"
        command = ["my-command", "--arg1"]
        run_everywhere.update_single_host(host, command)

        self.assertEqual(mock_subprocess_run.call_count, 3)

        # Expected calls for johntobin, root, and arianetobin
        expected_calls = [
            mock.call(
                [
                    "retry",
                    "--press_enter_before_retrying",
                    "0",
                    "johntobin@testhost",
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-t",
                    "johntobin@testhost",
                    "my-command",
                    "--arg1",
                ],
                check=False,
            ),
            mock.call(
                [
                    "retry",
                    "--press_enter_before_retrying",
                    "0",
                    "root@testhost",
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-t",
                    "johntobin@testhost",
                    "sudo",
                    "--login",
                    "my-command",
                    "--arg1",
                ],
                check=False,
            ),
            mock.call(
                [
                    "retry",
                    "--press_enter_before_retrying",
                    "0",
                    "arianetobin@testhost",
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-t",
                    "arianetobin@testhost",
                    "my-command",
                    "--arg1",
                ],
                check=False,
            ),
        ]

        mock_subprocess_run.assert_has_calls(expected_calls, any_order=False)

    @mock.patch.object(run_everywhere, "update_single_host")
    def test_main(self, mock_update_single_host: mock.Mock) -> None:
        argv = ["do-something", "arg"]
        return_code = run_everywhere.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_update_single_host.call_count, 3)

        expected_calls = [
            mock.call("laptop", ["do-something", "arg"]),
            mock.call("imac", ["do-something", "arg"]),
            mock.call("hosting", ["do-something", "arg"]),
        ]
        mock_update_single_host.assert_has_calls(expected_calls, any_order=True)

    def test_main_no_args(self) -> None:
        return_code = run_everywhere.main([])
        self.assertEqual(return_code, 1)

    @mock.patch.object(
        run_everywhere.shutil, "which", return_value="/usr/bin/caffeinate"
    )
    @mock.patch.object(run_everywhere.os, "execvp")
    def test_caffeinate_wrapper_activates(
        self, mock_execvp: mock.Mock, mock_which: mock.Mock
    ) -> None:
        with mock.patch.dict(run_everywhere.os.environ, {}, clear=True):
            run_everywhere.run_caffeinated(["/path/to/script", "arg1"])

            mock_which.assert_called_once_with("caffeinate")
            self.assertEqual(run_everywhere.os.environ["CAFFEINATED"], "do not sleep")
            mock_execvp.assert_called_once_with(
                "/usr/bin/caffeinate",
                ["/usr/bin/caffeinate", "-i", "/path/to/script", "arg1"],
            )

    @mock.patch.object(run_everywhere.os, "execvp")
    def test_caffeinate_wrapper_does_not_activate_if_set(
        self, mock_execvp: mock.Mock
    ) -> None:
        with mock.patch.dict(
            run_everywhere.os.environ, {"CAFFEINATED": "active"}, clear=True
        ):
            run_everywhere.run_caffeinated(["/path/to/script", "arg1"])
            mock_execvp.assert_not_called()

    @mock.patch.object(run_everywhere.shutil, "which", return_value=None)
    @mock.patch.object(run_everywhere.os, "execvp")
    def test_caffeinate_wrapper_does_not_activate_if_missing(
        self, mock_execvp: mock.Mock, mock_which: mock.Mock
    ) -> None:
        with mock.patch.dict(run_everywhere.os.environ, {}, clear=True):
            run_everywhere.run_caffeinated(["/path/to/script", "arg1"])
            mock_which.assert_called_once_with("caffeinate")
            mock_execvp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
