"""Tests for colx."""

import argparse
import unittest

import mock

import colx

class TestArgumentParsing(unittest.TestCase):
  """Tests for argument parsing."""

  def test_argument_parsing(self):
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
      for key in expected.iterkeys():
        self.assertEqual(getattr(actual, key), expected[key])

    # At least one column is required.
    with mock.patch('argparse.ArgumentParser.error') as mock_error:
      colx.parse_arguments(['asdf'])
      mock_error.assert_called_once_with(
          'At least one COLUMN argument is required.')
