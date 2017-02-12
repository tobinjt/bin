"""Tests for nines."""

import StringIO
import unittest

import mock
#  from pyfakefs import fake_filesystem_unittest

import nines


class TestNinesIntoPercent(unittest.TestCase):
  """Test converting 3.5 into 99.95."""

  def test_nines_into_percent(self):
    """Test nines_into_percent."""
    for nine, percent in [
        (1, 90),
        (2, 99),
        (2.5, 99.5),
        (3, 99.9),
        (4, 99.99),
        ]:
      self.assertEqual(percent, nines.nines_into_percent(nine))


class TestMain(unittest.TestCase):
  """Tests for main."""

  @mock.patch('sys.stdout', new_callable=StringIO.StringIO)
  def test_main(self, mock_stdout):
    """Test main."""
    nines.main(['argv0', '2', '7'])
    expected = ('99%: 315360 seconds (3 days, 15 hours, 36 minutes)\n'
                '99.99999%: 3.15359999652 seconds (3 seconds)\n')
    self.assertMultiLineEqual(expected, mock_stdout.getvalue())

if __name__ == '__main__':
  unittest.main()
