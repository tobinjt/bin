"""Tests for nines."""

import StringIO
import unittest

import mock
#  from pyfakefs import fake_filesystem_unittest

import nines


class TestMain(unittest.TestCase):
  """Tests for main."""

  @mock.patch('sys.stdout', new_callable=StringIO.StringIO)
  def test_main(self, mock_stdout):
    """Test main."""
    nines.main(['argv0', '2', '7'])
    expected = ('99%: 315360 seconds (3 days, 15 hours, 36 minutes)\n'
                '99.99999%: 3.1536 seconds (3 seconds)\n')
    self.assertEqual(expected, mock_stdout.getvalue())
