"""Tests for colx."""

import io
import unittest
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import colx


class TestArgumentParsing(unittest.TestCase):
    """Tests for argument parsing."""

    def test_successful_parsing(self):
        """Tests for argument parsing."""

        tests = [
            # Very simple test.
            (
                ["1", "asdf"],
                {
                    "columns": [1],
                    "filenames": ["asdf"],
                },
            ),
            # Negative index.
            (
                ["--", "-1", "asdf"],
                {
                    "columns": [-1],
                    "filenames": ["asdf"],
                },
            ),
            # The second digit should be a filename.
            # The second non-digit argument should be accepted.
            (
                ["1", "asdf", "2", "qwerty"],
                {
                    "columns": [1],
                    "filenames": ["asdf", "2", "qwerty"],
                },
            ),
            # Support ranges.
            (
                ["1:4", "asdf", "2"],
                {
                    "columns": [1, 2, 3, 4],
                    "filenames": ["asdf", "2"],
                },
            ),
            # Reversed ranges.
            (
                ["8:4", "asdf", "2"],
                {
                    "columns": [8, 7, 6, 5, 4],
                    "filenames": ["asdf", "2"],
                },
            ),
            # Negative ranges.
            (
                ["--", "-4:-1", "asdf", "2"],
                {
                    "columns": [-4, -3, -2, -1],
                    "filenames": ["asdf", "2"],
                },
            ),
            # Ranges with same start and end.
            (
                ["4:4", "asdf", "2"],
                {
                    "columns": [4],
                    "filenames": ["asdf", "2"],
                },
            ),
        ]
        for args, expected in tests:
            with self.subTest(f"Parsing {args}"):
                actual = colx.parse_arguments(argv=args)
                for key, value in expected.items():
                    self.assertEqual(value, getattr(actual, key))

    def test_error_checking(self):
        """Tests for error checking."""
        # At least one column is required.
        with mock.patch("argparse.ArgumentParser.error") as mock_error:
            colx.parse_arguments(argv=["asdf"])
            mock_error.assert_called_once_with(
                "At least one COLUMN argument is required."
            )

    @mock.patch("sys.exit")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_no_args(self, mock_stderr, mock_stdout, _):
        """Test no args."""
        colx.parse_arguments(argv=["argv0"])
        self.assertEqual("", mock_stdout.getvalue())
        # The name of the program is pytest when running tests.
        expected = (
            "usage: pytest [OPTIONS] COLUMN [COLUMNS] [FILES]\n"
            "pytest: error: At least one COLUMN argument is required.\n"
        )
        self.assertEqual(expected, mock_stderr.getvalue().replace("pytest-3", "pytest"))

    @mock.patch("sys.exit")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help(self, mock_stdout, _):
        """Test --help to ensure that the description is correctly set up."""
        colx.parse_arguments(argv=["argv0", "--help"])
        # The name of the program is pytest when running tests.
        substrings = [
            "usage: pytest [OPTIONS] COLUMN [COLUMNS] [FILES]\n",
            "\n\nExtract the specified columns from FILES or stdin.\n",
            "Column numbering starts at 1, not 0; column 0 is the entire line, "
            "just like awk.",
            "Negative column numbers are accepted; -1 is the last column",
            "Column ranges of the form 3:8, -3:1, 7:-7, and -1:-3 are accepted.",
            "COLUMNS_THEN_FILES    Any argument that looks like a column specifier",
            "remaining arguments are used as",
            "-d DELIMITER, --delimiter DELIMITER",
            " Regex delimiting input columns; ",
            "-s SEPARATOR, --separator SEPARATOR",
            " Separator between output columns",
            " backslash escape sequences will be expanded",
        ]
        stdout = mock_stdout.getvalue().replace("pytest-3", "pytest")
        for substring in substrings:
            with self.subTest(f"Testing -->>{substring}<<--"):
                self.assertIn(substring, stdout)


class TestProcessFiles(fake_filesystem_unittest.TestCase):
    """Tests for file processing."""

    def setUp(self):
        self.setUpPyfakefs()

    def test_simple(self):
        """Test basic processing."""
        filename = "input"
        with open(filename, "w", encoding="utf8") as tfh:
            tfh.write("one two three\n")
        output = colx.process_files(
            filenames=[filename], columns=[1, 3], delimiter=" ", separator=":"
        )
        self.assertEqual(["one:three"], output)

    def test_strip_empty_columns(self):
        """Test that empty leading and trailing columns are stripped."""
        for test_input, test_output in [
            ("  leading\n", "leading"),
            ("trailing  \n", "trailing"),
            ("  both \n", "both"),
        ]:
            filename = "input"
            with open(filename, "w", encoding="utf8") as tfh:
                tfh.write(test_input)
            output = colx.process_files(
                filenames=[filename], columns=[1, 2], delimiter=" ", separator=":"
            )
            self.assertEqual([test_output], output)

    def test_all_empty_columns(self):
        """Test behaviour when all columns are empty."""
        filename = "input"
        with open(filename, "w", encoding="utf8") as tfh:
            tfh.write("!!!!\n")
        output = colx.process_files(
            filenames=[filename], columns=[2, 3], delimiter="!", separator=":"
        )
        self.assertEqual([""], output)

    def test_column_too_large(self):
        """Test columns larger than input."""
        filename = "input"
        with open(filename, "w", encoding="utf8") as tfh:
            tfh.write("one two\n")
        output = colx.process_files(
            filenames=[filename], columns=[1, 2, 7], delimiter=" ", separator=":"
        )
        self.assertEqual(["one:two"], output)


class TestMain(fake_filesystem_unittest.TestCase):
    """Tests for main."""

    def setUp(self):
        self.setUpPyfakefs()

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main(self, mock_stdout):
        """Test main."""
        filename = "input"
        with open(filename, "w", encoding="utf8") as tfh:
            tfh.write("one two three\n")
        colx.main(argv=["argv0", "2", "1", filename])
        self.assertEqual("two one\n", mock_stdout.getvalue())


if __name__ == "__main__":  # pragma: no mutate
    unittest.main()
