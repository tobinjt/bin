"""Tests for colx."""

import unittest

import colx

class TestArgumentParsing(unittest.TestCase):
  """Tests for argument parsing."""

  def test_argument_parsing(self):
    """Tests for argument parsing."""

    tests = [
        (['1', 'asdf'],
         {
             'columns': [1],
             'filenames': ['asdf'],
         }),
    ]
    for (args, expected) in tests:
      actual = colx.parse_arguments(args)
      for key in expected.iterkeys():
        self.assertEqual(getattr(actual, key), expected[key])
