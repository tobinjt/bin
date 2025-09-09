"""Tests for nines."""

from io import StringIO
import sys
import unittest
from unittest import mock

import nines


class TestParsing(unittest.TestCase):
    """Test parsing."""

    def test_nines_into_percent(self):
        """Test nines_into_percent."""
        for nine, percent in [
            (0, 0),
            (0.5, 50),
            (1, 90),
            (2, 99),
            (2.0, 99),
            (2.5, 99.5),
            (3, 99.9),
            (4, 99.99),
        ]:
            self.assertEqual(percent, nines.nines_into_percent(num_nines=nine))

    def test_parse_nines_arg(self):
        """Test general parsing."""
        for nine, result in [
            ("0", 0),
            ("3", 99.9),
            ("7", 99.99999),
            ("20", 20),
            ("21", 21),
            ("80", 80),
            ("100", 100),
        ]:
            self.assertAlmostEqual(
                result, nines.parse_nines_arg(num_nines=nine), places=10
            )

        for nine, message in [
            ("as", "^Argument is not a number"),
            ("-5", "^You cannot have a negative uptime"),
            ("101", "^You cannot have more than 100% uptime"),
        ]:
            with self.assertRaisesRegex(ValueError, message):
                nines.parse_nines_arg(num_nines=nine)


class TestFormatting(unittest.TestCase):
    """Test formatting."""

    def test_strip_trailing_zeros(self):
        """Tests for strip_trailing_zeros."""
        self.assertEqual("123", nines.strip_trailing_zeros(number=123))
        self.assertEqual("123", nines.strip_trailing_zeros(number=123.0))
        self.assertEqual("10", nines.strip_trailing_zeros(number=10))
        self.assertEqual("10.1", nines.strip_trailing_zeros(number=10.1))
        self.assertEqual("0.1", nines.strip_trailing_zeros(number=0.1))

    def test_format_duration(self):
        """Tests for format_duration."""
        self.assertEqual("1 minute", nines.format_duration(seconds=60))
        self.assertEqual("2 minutes, 37 seconds", nines.format_duration(seconds=157))
        self.assertEqual("2 hours, 1 second", nines.format_duration(seconds=7201))


class TestMain(unittest.TestCase):
    """Tests for main."""

    @mock.patch.object(sys, "stdout", new_callable=StringIO)
    def test_main(self, mock_stdout: StringIO):
        """Test main."""
        for arg in ["2", "7"]:
            nines.main(argv=["argv0", arg])
        expected = [
            "99%: 315360 seconds (3 days, 15 hours, 36 minutes) per 365 days",
            "99.99999000000001%: 3.1535999965194605 seconds (3 seconds) per 365 ",
        ]
        output = mock_stdout.getvalue()
        for exp in expected:
            self.assertIn(exp, output)

    @mock.patch.object(nines, "parse_nines_arg", return_value=99)
    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=StringIO)
    @mock.patch.object(sys, "stderr", new_callable=StringIO)
    def test_no_args(
        self,
        mock_stderr: StringIO,
        _unused_moclstdout: StringIO,
        mock_exit: mock.Mock,
        _unused_mock_pna: mock.Mock,
    ):
        """Test no args."""
        nines.main(argv=["argv0"])
        # The name of the program is pytest when running tests.
        expected = (
            "usage: pytest NUMBER_OF_NINES [NUMBER_OF_DAYS]\n"
            "pytest: error: the following arguments are required: "
            "NUMBER_OF_NINES\n"
        )
        self.assertEqual(expected, mock_stderr.getvalue().replace("pytest-3", "pytest"))
        mock_exit.assert_called()

    @mock.patch.object(nines, "parse_nines_arg", return_value=99)
    @mock.patch.object(sys, "exit")
    @mock.patch.object(sys, "stdout", new_callable=StringIO)
    def test_help(
        self, mock_stdout: StringIO, mock_exit: mock.Mock, _unused_mock_pna: mock.Mock
    ):
        """Test --help to ensure that the description is correctly set up."""
        nines.main(argv=["argv0", "--help"])
        # The name of the program is pytest when running tests.
        substrings = [
            "usage: pytest NUMBER_OF_NINES [NUMBER_OF_DAYS]",
            "Display the number of seconds of downtime that N nines ",
            "Arguments >= 20 (e.g. 75) are interpreted as percentages",
            "arguments < 20 are interpreted as a number of nines.",
            "NUMBER_OF_NINES  See usage for details",
        ]
        # The position of newlines depends on the width of the terminal, so remove
        # them for consistency.
        stdout = mock_stdout.getvalue().replace("\n", " ").replace("pytest-3", "pytest")
        for substring in substrings:
            with self.subTest(f"Testing -->>{substring}<<--"):
                self.assertIn(substring, stdout)
        mock_exit.assert_called()


if __name__ == "__main__":  # pragma: no mutate
    unittest.main()
