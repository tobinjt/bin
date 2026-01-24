import io
import os
import pathlib
import tempfile
import unittest
from unittest import mock
import cron_to_plist

EXPECTED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>EnvironmentVariables</key>
\t<dict>
\t\t<key>PATH</key>
\t\t<string>/usr/bin:/bin</string>
\t</dict>
\t<key>Label</key>
\t<string>com.example.my-job</string>
\t<key>ProgramArguments</key>
\t<array>
\t\t<string>/bin/sh</string>
\t\t<string>-c</string>
\t\t<string>/usr/local/bin/my_script.sh</string>
\t</array>
\t<key>StandardErrorPath</key>
\t<string>/tmp/home/tmp/logs/launchd/com.example.my-job.err</string>
\t<key>StandardOutPath</key>
\t<string>/tmp/home/tmp/logs/launchd/com.example.my-job.out</string>
\t<key>StartCalendarInterval</key>
\t<dict>
\t\t<key>Hour</key>
\t\t<integer>2</integer>
\t\t<key>Minute</key>
\t\t<integer>30</integer>
\t</dict>
</dict>
</plist>
"""


class CronToPlistTest(unittest.TestCase):
    def test_create_plist_basic(self):
        """Tests a basic valid crontab line."""
        crontab_line = "30 2 * * * /path/to/script.sh"
        label = "com.example.test"
        plist = cron_to_plist.create_plist(crontab_line, label)
        self.assertEqual(plist.Label, label)
        self.assertEqual(
            plist.ProgramArguments, ["/bin/sh", "-c", "/path/to/script.sh"]
        )
        self.assertEqual(plist.StartCalendarInterval.Minute, 30)
        self.assertEqual(plist.StartCalendarInterval.Hour, 2)
        self.assertIsNone(plist.StartCalendarInterval.Day)
        self.assertIsNone(plist.StartCalendarInterval.Month)
        self.assertIsNone(plist.StartCalendarInterval.Weekday)

    def test_create_plist_daily(self):
        """Tests the @daily alias."""
        crontab_line = "@daily /path/to/daily.sh --extra-argument"
        label = "com.example.daily"
        plist = cron_to_plist.create_plist(crontab_line, label)
        self.assertEqual(plist.Label, label)
        self.assertEqual(
            plist.ProgramArguments,
            ["/bin/sh", "-c", "/path/to/daily.sh --extra-argument"],
        )
        self.assertEqual(plist.StartCalendarInterval.Minute, 0)
        self.assertEqual(plist.StartCalendarInterval.Hour, 0)
        self.assertIsNone(plist.StartCalendarInterval.Day)
        self.assertIsNone(plist.StartCalendarInterval.Month)
        self.assertIsNone(plist.StartCalendarInterval.Weekday)

    def test_create_plist_invalid_line(self):
        """Tests an invalid crontab line."""
        with self.assertRaisesRegex(
            ValueError, r"Expected 5 time fields and a command"
        ):
            cron_to_plist.create_plist("too few fields", "label")

    def test_create_plist_invalid_value(self):
        """Tests a crontab line with a non-integer value."""
        with self.assertRaisesRegex(
            ValueError, r"value 'a' for 'Minute' is not a simple integer"
        ):
            cron_to_plist.create_plist("a b c d e command", "label")

    @mock.patch.object(cron_to_plist.sys, "stderr", new_callable=io.StringIO)
    def test_main_failure(self, mock_stderr: io.StringIO):
        """Tests the main function with invalid arguments."""
        return_code = cron_to_plist.main(
            ["cron_to_plist.py", "-l", "com.test", "invalid cron line"]
        )
        self.assertEqual(return_code, 1)
        self.assertIn(
            "Error generating plist XML: Invalid crontab line.",
            mock_stderr.getvalue(),
        )

    @mock.patch.object(cron_to_plist.sys, "stdout", new_callable=io.StringIO)
    def test_main_output(self, mock_stdout: io.StringIO):
        """Tests that the main function prints the correct plist XML to stdout."""
        crontab_line = "30 2 * * * /usr/local/bin/my_script.sh"
        label = "com.example.my-job"
        # Mock the home directory for consistent path expansion in tests
        with (
            mock.patch.object(
                cron_to_plist.os.path, "expanduser", return_value="/tmp/home"
            ),
            mock.patch.dict(cron_to_plist.os.environ, {"PATH": "/usr/bin:/bin"}),
        ):
            cron_to_plist.main(["cron_to_plist.py", "-l", label, crontab_line])
            self.assertEqual(
                mock_stdout.getvalue().split("\n"), EXPECTED_XML.split("\n")
            )

    @mock.patch.object(cron_to_plist.sys, "stdout", new_callable=io.StringIO)
    @mock.patch.object(cron_to_plist, "expand_path")
    def test_main_write_flag(
        self,
        mock_expand_path: mock.Mock,
        mock_stdout: io.StringIO,
    ):
        """Tests the main function with the --write flag."""
        # Arrange
        # The plist file will be written here.
        launch_dir = tempfile.TemporaryDirectory()

        def expand_path_side_effect(path_str: str) -> cron_to_plist.pathlib.Path:
            if path_str == "~/tmp/logs/launchd":
                return pathlib.Path("/tmp/home/tmp/logs/launchd")
            if path_str == "~/Library/LaunchAgents":
                return pathlib.Path(launch_dir.name)
            return pathlib.Path(path_str)

        mock_expand_path.side_effect = expand_path_side_effect

        # Act
        crontab_line = "30 2 * * * /usr/local/bin/my_script.sh"
        label = "com.example.my-job"
        with mock.patch.dict(cron_to_plist.os.environ, {"PATH": "/usr/bin:/bin"}):
            return_code = cron_to_plist.main(
                ["cron_to_plist.py", "-l", label, "--write", crontab_line]
            )

        # Assert
        self.assertEqual(return_code, 0)
        self.assertTrue(os.path.exists(launch_dir.name))
        plist_file = pathlib.Path(launch_dir.name) / f"{label}.plist"
        with open(plist_file) as f:
            written_content = f.read()
        self.assertEqual(written_content.split("\n"), EXPECTED_XML.split("\n"))
        self.assertIn("Wrote plist to", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
