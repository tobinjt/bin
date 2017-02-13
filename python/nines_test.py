"""Tests for nines."""

import StringIO
import unittest

import mock
#  from pyfakefs import fake_filesystem_unittest

import nines


class TestParsing(unittest.TestCase):
  """Test parsing."""

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

  def test_parse_nines_arg(self):
    """Test general parsing."""
    for nine, message in [
        ('as', 'Argument is not a number'),
        ('-5', 'You cannot have a negative uptime'),
        ('453', 'You cannot have more than 100% uptime'),
        ]:
      self.assertRaisesRegexp(ValueError, message, nines.parse_nines_arg, nine)


class TestFormatting(unittest.TestCase):
  """Test formatting."""

  def test_strip_trailing_zeros(self):
    """Tests for strip_trailing_zeros."""
    self.assertEqual('123', nines.strip_trailing_zeros('123'))
    self.assertEqual('123', nines.strip_trailing_zeros('123.0'))
    self.assertEqual('10', nines.strip_trailing_zeros('10'))
    self.assertEqual('10.1', nines.strip_trailing_zeros('10.1'))

  def test_format_duration(self):
    """Tests for format_duration."""
    self.assertEqual('1 minute', nines.format_duration(60))
    self.assertEqual('2 minutes, 37 seconds', nines.format_duration(157))
    self.assertEqual('2 hours, 1 second', nines.format_duration(7201))


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
