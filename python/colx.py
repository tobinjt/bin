#!/usr/bin/env python

"""%(prog)s [OPTIONS] COLUMN [COLUMNS] [FILES]

Extract the specified columns from FILES or stdin.

Column numbering starts at 1, not 0; column 0 is the entire line, just like awk.
Column numbers that are out of bounds are silently ignored.  When each line is
split, empty leading or trailing columns will be discarded _before_ columns are
extracted.

Negative column numbers are accepted; -1 is the last column, -2 is the second
last, etc.  Note that negative column numbers may not behave as you expect when
files have a variable number of columns per line: e.g. in line 1 column -1 is
column 10, but in line 2 column -1 is column 5.
You need to put -- before the first negative column number, otherwise it will be
interpreted as a non-existent option.

Column ranges of the form 3:8, -3:1, 7:-7, and -1:-3 are accepted.  Both start
and end are required for each range.  It is not an error to specify an end point
that is out of bounds for a line, so 3:1000 will print all columns from 3
onwards (unless you have a *very* long line).
"""

import argparse
import fileinput
import re
import sys

__author__ = 'johntobin@johntobin.ie (John Tobin)'


def parse_arguments(argv):
  """Parse the arguments provided by the user.

  Args:
    argv: list(str), the arguments to parse.
  Returns:
    argparse.Namespace, with attributes set based on the arguments.
  """
  description = '\n'.join(__doc__.split('\n')[1:])
  usage = __doc__.split('\n')[0]

  argv_parser = argparse.ArgumentParser(
      description=description, usage=usage,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  argv_parser.add_argument(
      '-d', '--delimiter', default=r'\s+',
      help='Regex delimiting input columns; defaults to whitespace')
  argv_parser.add_argument(
      '-s', '--separator', default=' ',
      help='Separator between output columns; defaults to a single space; '
           'backslash escape sequences will be expanded')
  argv_parser.add_argument('args', nargs='*', metavar='COLUMNS_THEN_FILES',
                           help='Any argument that looks like a column '
                           'specifier is used as one, then remaining arguments'
                           ' are used as filenames')
  options = argv_parser.parse_args(argv)
  options.separator = options.separator.decode('string-escape')

  options.columns = []
  options.filenames = []
  remaining_args_are_filenames = False
  for arg in options.args:
    if remaining_args_are_filenames:
      options.filenames.append(arg)
      continue

    # Support 3:8 style columns.
    column_range = re.search(r'^(-?\d+):(-?\d+)$', arg)
    if column_range:
      first, last = int(column_range.group(1)), int(column_range.group(2))
      if first > last:
        increment = -1
        last -= 1
      else:
        increment = 1
        last += 1
      columns = range(first, last, increment)
      options.columns.extend(columns)
      continue

    try:
      column = int(arg)
      options.columns.append(column)
    except ValueError:
      remaining_args_are_filenames = True
      options.filenames.append(arg)

  if not options.columns:
    argv_parser.error('At least one COLUMN argument is required.')

  return options


def main(argv):
  options = parse_arguments(argv[1:])
  for line in fileinput.input(options.filenames):
    line = line.rstrip('\n')
    input_columns = [line]
    split_columns = re.split(options.delimiter, line)

    # Strip leading and trailing empty fields.
    first_index = 0
    while len(split_columns) > first_index and not split_columns[first_index]:
      first_index += 1
    last_index = len(split_columns) - 1
    while last_index > first_index and not split_columns[last_index]:
      last_index -= 1
    input_columns.extend(split_columns[first_index:last_index + 1])

    output_columns = []
    for column in options.columns:
      if abs(column) < len(input_columns):
        output_columns.append(input_columns[column])
    print options.separator.join(output_columns)


if __name__ == '__main__':
  main(sys.argv)
