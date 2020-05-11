"""Tests for check_website_resources."""

import logging
import subprocess
import textwrap
from typing import List, Text
import unittest

import mock
#  from pyfakefs import fake_filesystem_unittest

import check_website_resources


def split_inline_string(string: Text) -> List[Text]:
  """Split a multi-line inline string, stripping empty start and end lines."""
  return textwrap.dedent(string).strip().split('\n')


@mock.patch('subprocess.run')
@mock.patch('check_website_resources.read_wget_log')
class TestRunWget(unittest.TestCase):
  """Tests for run_wget."""

  def test_called_correctly(self, mock_read, mock_subprocess):
    """Test that subprocess.run is called correctly."""
    mock_read.return_value = ['foo bar baz\n']
    actual = check_website_resources.run_wget('asdf')
    self.assertEqual(mock_read.return_value, actual)
    mock_subprocess.assert_called_once_with(
        check_website_resources.WGET_ARGS + ['asdf'],
        check=True, capture_output=True)

  def test_process_fails(self, unused_mock_read, mock_subprocess):
    """Test that process failure is handled correctly."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=['blah'], stderr='wget: command not found')
    with self.assertLogs(level=logging.ERROR):
      actual = check_website_resources.run_wget('asdf')
      self.assertEqual([], actual)


@mock.patch('check_website_resources.run_wget')
class TestCheckSingleUrl(unittest.TestCase):
  """Tests for check_single_url."""

  def test_success(self, mock_run_wget):
    """TODO: WRITE ACTUAL TEST. Test for resources being correct."""
    mock_run_wget.return_value = ['TODO: WRITE ACTUAL TEST.']
    actual = check_website_resources.check_single_url(
        'asdf', [])
    self.assertEqual([], actual)

  def test_wget_fails(self, mock_run_wget):
    """Test for correctly handling wget failure."""
    mock_run_wget.return_value = []
    actual = check_website_resources.check_single_url(
        'asdf', [])
    self.assertEqual(['Running wget failed'], actual)

  def test_parsing(self, mock_run_wget):
    """Test parsing."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -x- ignore_this
        -- resource_2
        ignore this too
        -- foo bar return_baz
        """)
    actual = check_website_resources.check_single_url(
        'asdf', ['resource_1', 'resource_2', 'return_baz'])
    self.assertEqual([], actual)

  def test_extra_resource(self, mock_run_wget):
    """Test for there being an unexpected resource."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -- resource_2
        """)
    actual = check_website_resources.check_single_url(
        'asdf', ['resource_1'])
    expected = split_inline_string(
        """
        Unexpected resource diffs for asdf:
        --- expected
        +++ actual
        @@ -1 +1,2 @@
         resource_1
        +resource_2
        """)
    self.assertEqual(expected, actual)

if __name__ == '__main__':
  unittest.main()
