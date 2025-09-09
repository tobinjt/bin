"""Tests for check_backup_sentinels."""

from io import StringIO
import os
import sys
import time
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import check_backup_sentinels as cbs


class TestParseSentinels(fake_filesystem_unittest.TestCase):
    """Tests for parsing sentinels."""

    @override
    def setUp(self):
        self.setUpPyfakefs()

    def create_files_for_test(self, data: dict[str, str]) -> None:
        """Create files for tests."""
        for filename, contents in data.items():
            self.fs.create_file(filename, contents=contents)

    def test_simple(self):
        """Test basic processing."""
        testdir = "/test/test_simple"
        hostname = "a-hostname"
        base = os.path.join(testdir, hostname)
        files = {
            base: "1234\n",
            f"{base}.{cbs.SLEEPING_UNTIL}": "5432\n",
            f"{base}.{cbs.MAX_ALLOWED_DELAY}": "98\n",
        }
        self.create_files_for_test(files)
        parsed = cbs.parse_sentinels(directory=testdir, default_delay=7)
        self.assertEqual({hostname: 1234}, parsed.timestamps)
        self.assertEqual({hostname: 5432}, parsed.sleeping_until)
        self.assertEqual({hostname: 98}, parsed.max_allowed_delay)

    def test_default_delay(self):
        """Test default delay is used."""
        testdir = "/test/test_simple"
        hostname = "a-hostname"
        files = {
            os.path.join(testdir, hostname): "31313\n",
        }
        self.create_files_for_test(files)
        parsed = cbs.parse_sentinels(directory=testdir, default_delay=7)
        self.assertEqual({hostname: 31313}, parsed.timestamps)
        self.assertEqual({hostname: 7}, parsed.max_allowed_delay)
        self.assertEqual({hostname: 0}, parsed.sleeping_until)

    def test_bad_filename(self):
        """Test handling of bad filenames."""
        testdir = "/test/test_simple"
        hostname = "a-hostname"
        files = {
            f"{os.path.join(testdir, hostname)}.qwerty": "5432\n",
        }
        self.create_files_for_test(files)
        with self.assertRaisesRegex(cbs.Error, "^Bad format.*qwerty"):
            cbs.parse_sentinels(directory=testdir, default_delay=7)


class TestCheckSentinels(unittest.TestCase):
    """Tests for checking sentinels."""

    def test_no_sentinels(self):
        """Test that zero sentinels causes a warning."""
        sentinels = cbs.ParsedSentinels(
            cbs.SentinelMap({}), cbs.SentinelMap({}), cbs.SentinelMap({})
        )
        (warnings, messages) = cbs.check_sentinels(
            sentinels=sentinels, max_global_delay=11
        )
        expected = ["Zero sentinels passed, something is wrong."]
        self.assertEqual(expected, warnings)
        self.assertEqual(expected, messages)

    @mock.patch.object(time, "time")
    def test_all_backups_are_recent(self, mock_time: mock.Mock):
        """All backups are recent, no warnings."""
        host1 = "asdf"
        host2 = "qwerty"
        hour = 60 * 60
        timestamps = cbs.SentinelMap(
            {
                host1: 7 * hour,
                host2: 8 * hour,
            }
        )
        max_allowed_delay = cbs.SentinelMap(
            {
                host1: 2 * hour,
                host2: hour,
            }
        )
        sleeping_until = cbs.SentinelMap(
            {
                host1: 0,
                host2: 0,
            }
        )
        sentinels = cbs.ParsedSentinels(
            timestamps=timestamps,
            max_allowed_delay=max_allowed_delay,
            sleeping_until=sleeping_until,
        )
        mock_time.return_value = 8.5 * hour
        (warnings, _) = cbs.check_sentinels(sentinels=sentinels, max_global_delay=hour)
        self.assertEqual([], warnings)

    @mock.patch.object(time, "time")
    def test_all_backups_are_old(self, mock_time: mock.Mock):
        """All backups are old :("""
        host1 = "asdf"
        host2 = "qwerty"
        hour = 60 * 60
        timestamps = cbs.SentinelMap(
            {
                host1: 7 * hour,
                host2: 8 * hour,
            }
        )
        max_allowed_delay = cbs.SentinelMap(
            {
                host1: 2 * hour,
                host2: hour,
            }
        )
        sleeping_until = cbs.SentinelMap(
            {
                host1: 0,
                host2: 0,
            }
        )
        sentinels = cbs.ParsedSentinels(
            timestamps=timestamps,
            max_allowed_delay=max_allowed_delay,
            sleeping_until=sleeping_until,
        )
        mock_time.return_value = 12 * hour
        (warnings, messages) = cbs.check_sentinels(
            sentinels=sentinels, max_global_delay=hour
        )
        expected_warnings = [
            "All backups are delayed by at least 3600 seconds",
            'Backup for "asdf" too old:'
            + " current time 43200/1970-01-01 12:00;"
            + " last backup 25200/1970-01-01 07:00;"
            + " max allowed delay: 7200/1970-01-01 02:00;"
            + " delay allowed until: 32400/1970-01-01 09:00;"
            + " sleeping until: 0/1970-01-01 00:00",
            'Backup for "qwerty" too old:'
            + " current time 43200/1970-01-01 12:00;"
            + " last backup 28800/1970-01-01 08:00;"
            + " max allowed delay: 3600/1970-01-01 01:00;"
            + " delay allowed until: 32400/1970-01-01 09:00;"
            + " sleeping until: 0/1970-01-01 00:00",
        ]
        expected_messages = [
            warning.replace("too old", "debug info") for warning in expected_warnings
        ]
        # Do not truncate diffs.
        self.maxDiff = None
        self.assertEqual(expected_messages, messages)
        self.assertEqual(expected_warnings, warnings)

    @mock.patch.object(time, "time")
    def test_one_backup_is_old(self, mock_time: mock.Mock):
        """One backup (asdf) is old"""
        host1 = "asdf"
        host2 = "qwerty"
        host3 = "foobar"
        hour = 60 * 60
        timestamps = cbs.SentinelMap(
            {
                host1: 4 * hour,
                host2: 8 * hour,
                host3: 8 * hour,
            }
        )
        max_allowed_delay = cbs.SentinelMap(
            {
                host1: 2 * hour,
                host2: hour,
                host3: hour,
            }
        )
        sleeping_until = cbs.SentinelMap(
            {
                host1: 0,
                host2: 0,
                host3: 0,
            }
        )
        sentinels = cbs.ParsedSentinels(
            timestamps=timestamps,
            max_allowed_delay=max_allowed_delay,
            sleeping_until=sleeping_until,
        )
        mock_time.return_value = 8.5 * hour
        (warnings, messages) = cbs.check_sentinels(
            sentinels=sentinels, max_global_delay=hour
        )
        expected_warnings = [
            'Backup for "asdf" too old:'
            + " current time 30600/1970-01-01 08:30;"
            + " last backup 14400/1970-01-01 04:00;"
            + " max allowed delay: 7200/1970-01-01 02:00;"
            + " delay allowed until: 21600/1970-01-01 06:00;"
            + " sleeping until: 0/1970-01-01 00:00",
        ]
        # Do not truncate diffs.
        self.maxDiff = None
        self.assertEqual(expected_warnings, warnings)
        self.assertEqual(3, len(messages))

    @mock.patch.object(time, "time")
    def test_one_host_is_sleeping(self, mock_time: mock.Mock):
        """One host is sleeping, no warnings"""
        host1 = "asdf"
        host2 = "qwerty"
        hour = 60 * 60
        timestamps = cbs.SentinelMap(
            {
                host1: 4 * hour,
                host2: 8 * hour,
            }
        )
        max_allowed_delay = cbs.SentinelMap(
            {
                host1: 2 * hour,
                host2: 2 * hour,
            }
        )
        sleeping_until = cbs.SentinelMap(
            {
                host1: 8 * hour,
                host2: 0,
            }
        )
        sentinels = cbs.ParsedSentinels(
            timestamps=timestamps,
            max_allowed_delay=max_allowed_delay,
            sleeping_until=sleeping_until,
        )
        # 8 hours sleeping + 2 hours max delay > 9 hours current time.
        mock_time.return_value = 9 * hour
        (warnings, messages) = cbs.check_sentinels(
            sentinels=sentinels, max_global_delay=hour
        )
        # Do not truncate diffs.
        self.maxDiff: int | None = None
        self.assertEqual([], warnings)
        self.assertEqual(2, len(messages))


class TestMain(fake_filesystem_unittest.TestCase):
    """Tests for main."""

    TEST_DIR: str = "/test/dir"

    @override
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file(os.path.join(self.TEST_DIR, "qwerty"), contents="test test")

    def test_bad_args(self):
        """Check that bad args are rejected."""
        with self.assertRaisesRegex(cbs.Error, "^Usage:.*"):
            cbs.main(argv=["argv0"])
        with self.assertRaisesRegex(cbs.Error, "^Usage:.*"):
            cbs.main(argv=["argv0", "expected", "not expected"])
        with self.assertRaisesRegex(cbs.Error, "^Usage:.*"):
            cbs.main(argv=["argv0", "not a directory"])

    @mock.patch.object(sys, "exit")
    @mock.patch.object(cbs, "check_sentinels")
    @mock.patch.object(cbs, "parse_sentinels")
    def test_no_warnings(
        self, _unused_mock_parse: mock.Mock, mock_check: mock.Mock, mock_exit: mock.Mock
    ):
        """Check that good args are accepted."""
        mock_check.return_value = ([], [])
        with mock.patch.object(sys, "stderr", new_callable=StringIO) as mock_stderr:
            cbs.main(argv=["argv0", self.TEST_DIR])
            warnings = mock_stderr.getvalue()
            self.assertEqual("", warnings)
        mock_exit.assert_called_with(0)

    @mock.patch.object(sys, "exit")
    @mock.patch.object(cbs, "check_sentinels")
    @mock.patch.object(cbs, "parse_sentinels")
    def test_warnings_are_printed(
        self, _unused_mock_parse: mock.Mock, mock_check: mock.Mock, mock_exit: mock.Mock
    ):
        """Check that warnings are printed out."""
        expected = ["warning warning"]
        mock_check.return_value = (expected, [])
        with mock.patch.object(sys, "stderr", new_callable=StringIO) as mock_stderr:
            cbs.main(argv=["argv0", self.TEST_DIR])
            warnings = mock_stderr.getvalue()
            self.assertEqual(f"{expected[0]}\n", warnings)
        mock_exit.assert_called_with(1)

    @mock.patch.object(sys, "exit")
    @mock.patch.object(cbs, "check_sentinels")
    @mock.patch.object(cbs, "parse_sentinels")
    def test_messages_are_printed(
        self, _unused_mock_parse: mock.Mock, mock_check: mock.Mock, mock_exit: mock.Mock
    ):
        """Check that good args are accepted."""
        mock_check.return_value = (["warning warning"], ["message message"])
        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch.object(sys, "stdout", new_callable=StringIO) as mock_stdout:
                cbs.main(argv=["argv0", self.TEST_DIR])
                output = mock_stdout.getvalue()
                self.assertEqual("message message\n", output)
        mock_exit.assert_called_with(1)


class TestIntegration(fake_filesystem_unittest.TestCase):
    """Integration test."""

    @override
    def setUp(self):
        self.setUpPyfakefs()

    def create_files_for_test(self, data: dict[str, str]) -> None:
        """Create files for tests."""
        for filename, contents in data.items():
            self.fs.create_file(filename, contents=contents)

    @mock.patch.object(sys, "exit")
    @mock.patch.object(time, "time")
    def test_integration(self, mock_time: mock.Mock, mock_exit: mock.Mock):
        """Integration test that produces warnings."""
        testdir = "/test/check_sentinels"
        host1 = os.path.join(testdir, "asdf")
        host2 = os.path.join(testdir, "qwerty")
        day = 24 * 60 * 60
        files = {
            host1: str(7 * day),
            host2: str(8 * day),
            f"{host1}.{cbs.MAX_ALLOWED_DELAY}": str(day),
            f"{host2}.{cbs.MAX_ALLOWED_DELAY}": str(2 * day),
        }
        self.create_files_for_test(files)
        mock_time.return_value = 8.5 * day
        with mock.patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with mock.patch.object(sys, "stderr", new_callable=StringIO) as mock_stderr:
                cbs.main(argv=["argv0", testdir])
                messages = mock_stdout.getvalue()
                warnings = mock_stderr.getvalue()
                expected = (
                    'Backup for "asdf" too old:'
                    " current time 734400/1970-01-09 12:00;"
                    " last backup 604800/1970-01-08 00:00;"
                    " max allowed delay: 86400/1970-01-02 00:00;"
                    " delay allowed until: 691200/1970-01-09 00:00;"
                    " sleeping until: 0/1970-01-01 00:00\n"
                )
                self.assertEqual(expected, warnings)
                self.assertEqual("", messages)
        mock_exit.assert_called_with(1)


if __name__ == "__main__":  # pragma: no mutate
    unittest.main()
