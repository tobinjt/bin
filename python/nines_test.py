"""Tests for nines."""

from io import StringIO
import unittest

import mock

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
      self.assertEqual(percent, nines.nines_into_percent(nine))

  def test_parse_nines_arg(self):
    """Test general parsing."""
    self.assertEqual(0, nines.parse_nines_arg('0'))
    self.assertEqual(21, nines.parse_nines_arg('21'))
    self.assertEqual(80, nines.parse_nines_arg('80'))
    self.assertEqual(100, nines.parse_nines_arg('100'))
    for nine, message in [
        ('as', '^Argument is not a number'),
        ('-5', '^You cannot have a negative uptime'),
        ('101', '^You cannot have more than 100% uptime'),
        ]:
      self.assertRaisesRegex(ValueError, message, nines.parse_nines_arg, nine)


class TestFormatting(unittest.TestCase):
  """Test formatting."""

  def test_strip_trailing_zeros(self):
    """Tests for strip_trailing_zeros."""
    self.assertEqual('123', nines.strip_trailing_zeros('123'))
    self.assertEqual('123', nines.strip_trailing_zeros('123.0'))
    self.assertEqual('10', nines.strip_trailing_zeros('10'))
    self.assertEqual('10.1', nines.strip_trailing_zeros('10.1'))
    self.assertEqual('.1', nines.strip_trailing_zeros('.1'))

  def test_format_duration(self):
    """Tests for format_duration."""
    self.assertEqual('1 minute', nines.format_duration(60))
    self.assertEqual('2 minutes, 37 seconds', nines.format_duration(157))
    self.assertEqual('2 hours, 1 second', nines.format_duration(7201))


class TestMain(unittest.TestCase):
  """Tests for main."""

  @mock.patch('sys.stdout', new_callable=StringIO)
  def test_main(self, mock_stdout):
    """Test main."""
    nines.main(['argv0', '2', '7'])
    expected = ['99%: 315360 seconds (3 days, 15 hours, 36 minutes)\n',
                '99.99999', '3.1535999965', '(3 seconds)\n']
    output = mock_stdout.getvalue()
    for exp in expected:
      self.assertIn(exp, output)

  @mock.patch('sys.exit')
  @mock.patch('sys.stdout', new_callable=StringIO)
  @mock.patch('sys.stderr', new_callable=StringIO)
  def test_no_args(self, mock_stderr, mock_stdout, _):
    """Test main."""
    nines.main(['argv0'])
    self.assertEqual('', mock_stdout.getvalue())
    # The name of the program is pytest when running tests.
    expected = ('usage: pytest NUMBER_OF_NINES [NUMBER_OF_NINES . . .]\n'
                'pytest: error: the following arguments are required: '
                'NUMBER_OF_NINES\n')
    self.assertEqual(expected, mock_stderr.getvalue())

  @mock.patch('sys.exit')
  @mock.patch('sys.stdout', new_callable=StringIO)
  def test_help(self, mock_stdout, _):
    """Test --help to ensure that the description is correctly set up."""
    nines.main(['argv0', '--help'])
    # The name of the program is pytest when running tests.
    substrings = ['usage: pytest NUMBER_OF_NINES [NUMBER_OF_NINES . . .]',
                  'Display the number of seconds of downtime that N nines ',
                  'Arguments >= 20 (e.g. 75) are interpreted as percentages',
                  'arguments < 20 are interpreted as a number of nines.',
                  'NUMBER_OF_NINES  See usage for details',
                  ]
    # The position of newlines depends on the width of the terminal, so remove
    # them for consistency.
    stdout = mock_stdout.getvalue().replace('\n', ' ')
    for substring in substrings:
      self.assertIn(substring, stdout)


if __name__ == '__main__':  # pragma: no mutate
  unittest.main()
