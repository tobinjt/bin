#!/usr/bin/env python

"""Usage: %(prog)s NUMBER_OF_NINES [NUMBER_OF_NINES . . .]

Display the number of seconds of downtime that N nines uptime allows.  Uptime is
usually described as N nines, e.g. 3 nines is 99.9%% uptime, 6 nines is
99.9999%% uptime.  This program displays how much downtime per year is allowed
by N nines uptime, e.g. 6 nines uptime allows 31.536 seconds per year of
downtime.

Arguments >= %(PT)s (e.g. 75) are interpreted as percentages, arguments < %(PT)s
are interpreted as a number of nines.
"""

__author__ = 'johntobin@johntobin.ie (John Tobin)'

import itertools
import sys


# Args >= PERCENT_THRESHOLD are interpreted as percentages, < PERCENT_THRESHOLD
# are interpreted as a number of nines.
PERCENT_THRESHOLD = 20


def strip_trailing_zeros(number):
  """Strip unnecessary trailing zeros from a number.

  %d formats integers only.  %f formats floats, but has way too many digits.
  There's no format suitable for displaying a number that might be a floar or an
  integer, hence this function.

  Args:
    number: a number, either an integer or a string

  Returns:
    A string representing number, with any unnecessary trailing zeros removed.
  """
  string = str(number)
  if string.find('.') != -1:
    string = string.rstrip('0').rstrip('.')
  return string


def format_duration(seconds):
  """Format a number of seconds as "x hours, y minutes, z seconds".

  Args:
    seconds: int, number of seconds.
  Returns:
    str, string to print.
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


def parse_nines_arg(num_nines):
  """Parse an CLI argument, converting it into a percentage.

  Args:
    num_nines: str(num), argument to parse.
  Returns:
    float, parsed nines value.
  Raises:
    ValueError, when an invalid argument is provided.
  """
  orig_num_nines = num_nines
  try:
    num_nines = float(num_nines)
  except ValueError:
    raise ValueError('Argument is not a number: %s' % num_nines)
  if num_nines < 0:
    raise ValueError('You cannot have a negative uptime: %s' % orig_num_nines)
  if num_nines > 100:
    raise ValueError('You cannot have more than 100%% uptime: %s'
                     % orig_num_nines)
  if num_nines >= PERCENT_THRESHOLD:
    return num_nines
  return nines_into_percent(num_nines)


def nines_into_percent(num_nines):
  """Turn 3.5 into 99.95.

  1 -> 90
  2 -> 99
  2.5 -> 99.5
  3 -> 99.9
  4 -> 99.99

  Args:
    num_nines: float, argument to parse.
  Returns:
    float, parsed nines value.
  """
  num, remainder = divmod(num_nines, 1)
  digits = ['0.'] + list(itertools.repeat('9', int(num)))
  # 0 -> '', 0.5 -> 5
  digits.append(str(remainder).lstrip('0.').lstrip('.'))
  result = 100 * float(''.join(digits))
  return result


def nines(num_nines):
  """Calculate nines for a number

  Args:
    num_nines: float, nines to calculate.
  Returns:
    str, result to print.
  """
  downtime_fraction = (100 - num_nines) / 100
  seconds_per_year = 60 * 60 * 24 * 365
  downtime_seconds = downtime_fraction * seconds_per_year

  return ('%s%%: %s seconds (%s)'
          % (strip_trailing_zeros(num_nines),
             strip_trailing_zeros(downtime_seconds),
             format_duration(downtime_seconds)))

def main(argv):
  # TODO: use argparse.
  if len(argv) <= 1:
    sys.exit(__doc__ % {
        'prog': argv[0],
        'PT': PERCENT_THRESHOLD,
        })

  for num_nines in argv[1:]:
    print nines(parse_nines_arg(num_nines))

if __name__ == '__main__':
  main(sys.argv)