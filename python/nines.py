#!/usr/bin/env python3

"""%(prog)s NUMBER_OF_NINES [NUMBER_OF_NINES . . .]

Display the number of seconds of downtime that N nines uptime allows.  Uptime is
usually described as N nines, e.g. 3 nines is 99.9%% uptime, 6 nines is
99.9999%% uptime.  This program displays how much downtime per year is allowed
by N nines uptime, e.g. 6 nines uptime allows 31.536 seconds per year of
downtime.

Arguments >= %(PT)s (e.g. 75) are interpreted as percentages, arguments < %(PT)s
are interpreted as a number of nines.
"""

__author__ = 'johntobin@johntobin.ie (John Tobin)'

import argparse
import itertools
import sys
from typing import List


# Args >= PERCENT_THRESHOLD are interpreted as percentages, < PERCENT_THRESHOLD
# are interpreted as a number of nines.
PERCENT_THRESHOLD = 20


def strip_trailing_zeros(number: float) -> str:
  """Strip unnecessary trailing zeros from a number.

  %d formats integers only.  %f formats floats, but has way too many digits.
  There's no format suitable for displaying a number that might be a float or an
  integer, hence this function.

  Args:
    number: a number

  Returns:
    Number, with any unnecessary trailing zeros removed.
  """
  string = str(number)
  if string.find('.') != -1:
    string = string.rstrip('0').rstrip('.')
  return string


def format_duration(seconds: float) -> str:
  """Format a number of seconds as "x hours, y minutes, z seconds".

  Args:
    seconds: number of seconds.
  Returns:
    string to print.
  """
  time_units = {}
  seconds_so_far = 1
  for (number, label) in ((1, 'second'),
                          (60, 'minute'),
                          (60, 'hour'),
                          (24, 'day'),
                          (365, 'year')):
    seconds_so_far *= number
    time_units[seconds_so_far] = label

  durations = []
  for seconds_per_time_unit in sorted(time_units, reverse=True):
    if seconds_per_time_unit <= seconds:
      num_time_units, seconds = divmod(seconds, seconds_per_time_unit)
      plural = ''
      if num_time_units > 1:
        plural = 's'
      durations.append('%d %s%s' % (num_time_units,
                                    time_units[seconds_per_time_unit],
                                    plural))
  return ', '.join(durations)


def parse_nines_arg(num_nines: str) -> float:
  """Parse an CLI argument, converting it into a percentage.

  Args:
    num_nines: argument to parse.
  Returns:
    parsed nines value.
  Raises:
    ValueError, when an invalid argument is provided.
  """
  try:
    parsed_num_nines = float(num_nines)
  except ValueError:
    raise ValueError('Argument is not a number: %s' % num_nines)
  if parsed_num_nines < 0:
    raise ValueError('You cannot have a negative uptime: %s' % num_nines)
  if parsed_num_nines > 100:
    raise ValueError('You cannot have more than 100%% uptime: %s' % num_nines)
  if parsed_num_nines >= PERCENT_THRESHOLD:
    return parsed_num_nines
  return nines_into_percent(parsed_num_nines)


def nines_into_percent(num_nines: float) -> float:
  """Turn 3.5 into 99.95.

  1 -> 90
  2 -> 99
  2.5 -> 99.5
  3 -> 99.9
  4 -> 99.99

  Args:
    num_nines: argument to parse.
  Returns:
    parsed nines value.
  """
  num, remainder = divmod(num_nines, 1)
  digits = ['0.'] + list(itertools.repeat('9', int(num)))
  # 0 -> '', 0.5 -> 5
  digits.append(str(remainder).lstrip('0.').lstrip('.'))
  result = 100 * float(''.join(digits))
  return result


def nines(num_nines: float) -> str:
  """Calculate nines for a number

  Args:
    num_nines: nines to calculate.
  Returns:
    result to print.
  """
  downtime_fraction = (100 - num_nines) / 100
  seconds_per_year = 60 * 60 * 24 * 365
  downtime_seconds = downtime_fraction * seconds_per_year

  return ('%s%%: %s seconds (%s)'
          % (strip_trailing_zeros(num_nines),
             strip_trailing_zeros(downtime_seconds),
             format_duration(downtime_seconds)))

def main(argv: List[str]) -> None:
  description = '\n'.join(__doc__.split('\n')[1:]) % {
      'PT': PERCENT_THRESHOLD,
  }
  usage = __doc__.split('\n')[0]
  argv_parser = argparse.ArgumentParser(
      description=description, usage=usage)
  argv_parser.add_argument('args', nargs='+', metavar='NUMBER_OF_NINES',
                           default=[], help='See usage for details')
  options = argv_parser.parse_args(argv[1:])

  for num_nines in options.args:
    print(nines(parse_nines_arg(num_nines)))

if __name__ == '__main__':
  main(sys.argv)
