"""Tests for colx."""

from io import StringIO
import unittest

import mock
from pyfakefs import fake_filesystem_unittest

import colx

class TestArgumentParsing(unittest.TestCase):
  """Tests for argument parsing."""

  def test_successful_parsing(self):
    """Tests for argument parsing."""

    tests = [
        # Very simple test.
        (['1', 'asdf'],
         {
             'columns': [1],
             'filenames': ['asdf'],
         }),
        # Negative index.
        (['--', '-1', 'asdf'],
         {
             'columns': [-1],
             'filenames': ['asdf'],
         }),
        # The second digit should be a filename.
        (['1', 'asdf', '2'],
         {
             'columns': [1],
             'filenames': ['asdf', '2'],
         }),
        # Support ranges.
        (['1:4', 'asdf', '2'],
         {
             'columns': [1, 2, 3, 4],
             'filenames': ['asdf', '2'],
         }),
        # Reversed ranges.
        (['8:4', 'asdf', '2'],
         {
             'columns': [8, 7, 6, 5, 4],
             'filenames': ['asdf', '2'],
         }),
        # Negative ranges.
        (['--', '-4:-1', 'asdf', '2'],
         {
             'columns': [-4, -3, -2, -1],
             'filenames': ['asdf', '2'],
         }),
    ]
    for (args, expected) in tests:
      actual = colx.parse_arguments(args)
      for key in expected:
        self.assertEqual(getattr(actual, key), expected[key])

  def test_error_checking(self):  # pylint: disable=no-self-use
    """Tests for error checking."""
    # At least one column is required.
    with mock.patch('argparse.ArgumentParser.error') as mock_error:
      colx.parse_arguments(['asdf'])
      mock_error.assert_called_once_with(
          'At least one COLUMN argument is required.')


class TestProcessFiles(fake_filesystem_unittest.TestCase):
  """Tests for file processing."""

  def setUp(self):
    self.setUpPyfakefs()

  def test_simple(self):
    """Test basic processing."""
    filename = 'input'
    with open(filename, 'w') as tfh:
      tfh.write('one two three\n')
    output = colx.process_files([filename], [1, 3], ' ', ':')
    self.assertEqual(['one:three'], output)

  def test_strip_empty_columns(self):
    """Test that empty leading and trailing columns are stripped."""
    filename = 'input'
    with open(filename, 'w') as tfh:
      tfh.write('  one two  \n')
    output = colx.process_files([filename], [2], ' ', ':')
    self.assertEqual(['two'], output)

  def test_column_too_large(self):
    """Test columns larger than input."""
    filename = 'input'
    with open(filename, 'w') as tfh:
      tfh.write('one two\n')
    output = colx.process_files([filename], [1, 2, 7], ' ', ':')
    self.assertEqual(['one:two'], output)


class TestMain(fake_filesystem_unittest.TestCase):
  """Tests for main."""

  def setUp(self):
    self.setUpPyfakefs()

  @mock.patch('sys.stdout', new_callable=StringIO)
  def test_main(self, mock_stdout):
    """Test main."""
    filename = 'input'
    with open(filename, 'w') as tfh:
      tfh.write('one two three\n')
    colx.main(['argv0', '2', '1', filename])
    self.assertEqual('two one\n', mock_stdout.getvalue())

if __name__ == '__main__':  # pragma: no mutate
  unittest.main()
