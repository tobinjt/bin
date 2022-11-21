#!/usr/bin/env python3
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
from typing import List

__author__ = "johntobin@johntobin.ie (John Tobin)"


def parse_arguments(*, argv: List[str]) -> argparse.Namespace:
    """Parse the arguments provided by the user.

    Args:
        argv: the arguments to parse.
    Returns:
        argparse.Namespace, with attributes set based on the arguments.
    """
    (usage, description) = __doc__.split("\n", maxsplit=1)
    argv_parser = argparse.ArgumentParser(
        description=description,
        usage=usage,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    argv_parser.add_argument(
        "-d",
        "--delimiter",
        default=r"\s+",
        help="Regex delimiting input columns; defaults to whitespace")
    argv_parser.add_argument(
        "-s",
        "--separator",
        default=" ",
        help="Separator between output columns; defaults to a single space; "
        "backslash escape sequences will be expanded")
    argv_parser.add_argument(
        "args",
        nargs="*",
        metavar="COLUMNS_THEN_FILES",
        help="Any argument that looks like a column "
        "specifier is used as one, then remaining arguments"
        " are used as filenames")
    options = argv_parser.parse_args(argv)
    options.separator = bytes(options.separator, "utf-8").decode("unicode_escape")

    options.columns = []
    options.filenames = []
    # mutmut mutates this to '= None', which evaluates to False in a boolean
    # context, so it's a meaningless mutation.
    remaining_args_are_filenames = False  # pragma: no mutate
    for arg in options.args:
        if remaining_args_are_filenames:
            options.filenames.append(arg)
            continue

        # Support 3:8 style columns.
        column_range = re.search(r"^(-?\d+):(-?\d+)$", arg)
        if column_range:
            first, last = int(column_range.group(1)), int(column_range.group(2))
            # mutmut mutates this to 'first >= last', which isn't useful, because if
            # 'first == last' then the increments don't matter.
            if first > last:  # pragma: no mutate
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
        argv_parser.error("At least one COLUMN argument is required.")

    return options


def process_files(*, filenames: List[str], columns: List[int], delimiter: str,
                  separator: str) -> List[str]:
    """Process files and return specified columns.

    Args:
        filenames: list of files to process.  If empty, sys.stdin will be processed.
        columns: columns to output.
        delimiter: delimiter for splitting input lines into columns.
        separator: separator for combining columns into output lines.
    Returns:
        strings to output.
    """
    output = []
    for line in fileinput.input(filenames):
        line = line.rstrip("\n")  # pragma: no mutate
        input_columns = [line]
        split_columns = re.split(delimiter, line)

        # Strip leading and trailing empty fields.
        first_index = 0
        while len(split_columns) > first_index and not split_columns[first_index]:
            # mutmut mutates this to 'first_index = 1', which causes an infinite loop.
            first_index += 1  # pragma: no mutate
        last_index = len(split_columns) - 1
        # mutmut mutates '>' to '>=' and vice versa.  There is a test for handling
        # empty input, and that's the only way that the indices could overlap, so I
        # know this is safe either way.
        while (last_index > first_index  # pragma: no mutate
               and not split_columns[last_index]):
            # mutmut mutates this to 'last_index = 1', which causes an infinite loop.
            last_index -= 1  # pragma: no mutate
        input_columns.extend(split_columns[first_index:last_index + 1])

        output_columns = []
        for column in columns:
            if abs(column) < len(input_columns):
                output_columns.append(input_columns[column])
        output.append(separator.join(output_columns))

    return output


def main(*, argv: List[str]) -> None:
    options = parse_arguments(argv=argv[1:])
    output = process_files(filenames=options.filenames,
                           columns=options.columns,
                           delimiter=options.delimiter,
                           separator=options.separator)
    for line in output:
        print(line)


if __name__ == "__main__":  # pragma: no mutate
    main(argv=sys.argv)
