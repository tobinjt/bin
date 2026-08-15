import unittest
from unittest import mock

import run_everywhere


class RunEverywhereTest(unittest.TestCase):
    """Tests for the run_everywhere script."""

    def test_host_user_map_bidirectional(self) -> None:
        """Tests that HostUserMap populates host_to_users and user_to_hosts correctly."""
        mapping = {
            "h1": ["u1", "u2"],
            "h2": ["u2", "u3"],
        }
        host_map = run_everywhere.HostUserMap.from_host_to_users(mapping)
        self.assertEqual(host_map.host_to_users, mapping)
        self.assertEqual(
            host_map.user_to_hosts,
            {
                "u1": ["h1"],
                "u2": ["h1", "h2"],
                "u3": ["h2"],
            },
        )
        self.assertEqual(host_map.get_all_hosts(), ["h1", "h2"])
        self.assertEqual(host_map.get_all_users(), ["u1", "u2", "u3"])

    def test_host_user_map_filter_targets(self) -> None:
        """Tests filtering targets by presence of host or user in flags."""
        mapping = {
            "h1": ["u1", "u2"],
            "h2": ["u2", "u3"],
            "h3": ["u4"],
        }
        host_map = run_everywhere.HostUserMap.from_host_to_users(mapping)

        # Matching by host only
        res = host_map.filter_targets(["h1"], [])
        self.assertEqual(res, {"h1": ["u1", "u2"]})

        # Matching by user only
        res = host_map.filter_targets([], ["u3"])
        self.assertEqual(res, {"h2": ["u3"]})

        # Matching by either host or user
        res = host_map.filter_targets(["h1"], ["u3"])
        self.assertEqual(res, {"h1": ["u1", "u2"], "h2": ["u3"]})

    @mock.patch.object(run_everywhere.subprocess, "run")
    def test_update_single_host(self, mock_subprocess_run: mock.Mock) -> None:
        """
        Tests that the correct SSH commands are constructed and run for a single host.
        """
        host = "testhost"
        command = ["my-command", "--arg1"]
        users = ["johntobin", "root", "arianetobin"]
        run_everywhere.update_single_host(host, users, command)

        self.assertEqual(mock_subprocess_run.call_count, 3)

        # Expected calls for johntobin, root, and arianetobin
        expected_calls = [
            mock.call(
                [
                    "retry",
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-o",
                    "ForwardAgent=yes",
                    "-t",
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
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-o",
                    "ForwardAgent=yes",
                    "-t",
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
                    "ssh",
                    "-o",
                    "ControlMaster=no",
                    "-o",
                    "ForwardAgent=yes",
                    "-t",
                    "-t",
                    "arianetobin@testhost",
                    "my-command",
                    "--arg1",
                ],
                check=False,
            ),
        ]

        mock_subprocess_run.assert_has_calls(expected_calls, any_order=False)

    @mock.patch.object(run_everywhere.subprocess, "run")
    def test_update_single_host_localhost(self, mock_subprocess_run: mock.Mock) -> None:
        """
        Tests that SSH is not used when host is localhost.
        """
        host = "localhost"
        command = ["my-command", "--arg1"]
        users = ["johntobin", "root"]
        run_everywhere.update_single_host(host, users, command)

        self.assertEqual(mock_subprocess_run.call_count, 2)

        # Expected calls for johntobin and root on localhost
        expected_calls = [
            mock.call(
                [
                    "retry",
                    "my-command",
                    "--arg1",
                ],
                check=False,
            ),
            mock.call(
                [
                    "retry",
                    "sudo",
                    "--login",
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
        self.assertEqual(mock_update_single_host.call_count, 4)

        expected_calls = [
            mock.call("laptop", ["johntobin", "root"], ["do-something", "arg"]),
            mock.call(
                "imac",
                ["johntobin", "root", "arianetobin"],
                ["do-something", "arg"],
            ),
            mock.call(
                "hosting",
                ["johntobin", "root", "arianetobin"],
                ["do-something", "arg"],
            ),
            mock.call("truenas", ["truenas_admin"], ["do-something", "arg"]),
        ]
        mock_update_single_host.assert_has_calls(expected_calls, any_order=True)

    @mock.patch.object(run_everywhere, "update_single_host")
    def test_main_minus_minus(self, mock_update_single_host: mock.Mock) -> None:
        # -- should be ignored.
        argv = ["--", "do-something", "arg"]
        return_code = run_everywhere.main(argv)

        self.assertEqual(return_code, 0)
        self.assertEqual(mock_update_single_host.call_count, 4)

        expected_calls = [
            mock.call("laptop", ["johntobin", "root"], ["do-something", "arg"]),
            mock.call(
                "imac",
                ["johntobin", "root", "arianetobin"],
                ["do-something", "arg"],
            ),
            mock.call(
                "hosting",
                ["johntobin", "root", "arianetobin"],
                ["do-something", "arg"],
            ),
            mock.call("truenas", ["truenas_admin"], ["do-something", "arg"]),
        ]
        mock_update_single_host.assert_has_calls(expected_calls, any_order=True)

    def test_main_no_args(self) -> None:
        return_code = run_everywhere.main([])
        self.assertEqual(return_code, 1)

    def test_parse_args_no_args_raises(self) -> None:
        with self.assertRaisesRegex(run_everywhere.UsageError, "No command specified"):
            run_everywhere.parse_args([])

    def test_parse_args_unrecognized_host_raises(self) -> None:
        with self.assertRaisesRegex(
            run_everywhere.UsageError, "Unrecognized host\\(s\\): unknown_host"
        ):
            run_everywhere.parse_args(["--hosts", "unknown_host", "my-command"])

    def test_parse_args_unrecognized_user_raises(self) -> None:
        with self.assertRaisesRegex(
            run_everywhere.UsageError, "Unrecognized user\\(s\\): unknown_user"
        ):
            run_everywhere.parse_args(["--users", "unknown_user", "my-command"])

    def test_parse_args_unrecognized_host_and_user_raises(self) -> None:
        regex = (
            "Unrecognized host\\(s\\): unknown_host\n"
            "Unrecognized user\\(s\\): unknown_user"
        )
        with self.assertRaisesRegex(run_everywhere.UsageError, regex):
            run_everywhere.parse_args(
                [
                    "--hosts",
                    "unknown_host",
                    "--users",
                    "unknown_user",
                    "my-command",
                ]
            )

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
