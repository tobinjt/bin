#!/usr/bin/env python

"""Display the number of seconds of downtime that N nines uptime allows.

Uptime is usually described as N nines, e.g. 3 nines is 99.9% uptime, 6 nines is
99.9999% uptime.  This program displays how much downtime per year is allowed by
N nines uptime, e.g. 6 nines uptime allows 31.536 seconds per year of downtime.
"""

__author__ = 'johntobin@johntobin.ie (John Tobin)'

import sys


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
  """Format a number of seconds as "x hours, y minutes, z seconds"."""
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


def nines(num_nines):
  """Calculate nines for a number

  Args:
    num_nines: str, either N or N%.
  Returns:
    str, result to print.
  """
  orig_num_nines = num_nines
  if num_nines[-1] == '%':
    num_nines_is_percentage = True
    num_nines = num_nines[:-1]
  else:
    num_nines_is_percentage = False

  try:
    num_nines = float(num_nines)
  except ValueError:
    sys.exit('Argument is not a number: %s' % str(num_nines))

  if num_nines < 0:
    sys.exit('You cannot have a negative downtime: %s' % orig_num_nines)
  if num_nines_is_percentage:
    if num_nines > 100:
      sys.exit('You cannot have more that 100%% uptime: %s' % orig_num_nines)
    downtime_fraction = (100 - num_nines) / 100
    uptime_percentage = num_nines
  else:
    downtime_fraction = 10 ** -num_nines
    uptime_percentage = 100 * (1 - downtime_fraction)

  seconds_per_year = 60 * 60 * 24 * 365
  downtime_seconds = downtime_fraction * seconds_per_year

  return ('%s%%: %s seconds (%s)'
          % (strip_trailing_zeros(uptime_percentage),
             strip_trailing_zeros(downtime_seconds),
             format_duration(downtime_seconds)))

def main(argv):
  if len(argv) <= 1:
    sys.exit(
        """Usage: %s NUMBER_OF_NINES [NUMBER_OF_NINES . . .]
When NUMBER_OF_NINES ends with %%, it is a raw percentage.
When NUMBER_OF_NINES does not end with %%, it is the number of nines, e.g:
  3 => 99.9%%, 7 => 99.99999%%"""
        % argv[0])

  for num_nines in argv[1:]:
    print nines(num_nines)

if __name__ == '__main__':
  main(sys.argv)
