#!/usr/bin/env python3

"""%(prog)s [OPTIONS] DIRECTORY

Check sentinel times for all files in DIRECTORY.

Files in DIRECTORY:
  - HOSTNAME: the sentinel file for HOSTNAME.  Contains seconds since the epoch.
  - HOSTNAME.sleeping_until: when is HOSTNAME expected to wake up, e.g. while
    we're travelling and a laptop is at home.  Contains seconds since the epoch.
  - HOSTNAME.max_allowed_delay: max delay, in days, for backups from HOSTNAME.
    Contains a number of days, e.g. 3 or 7
TODO: write more.
"""

import fileinput
import glob
import os
import re
import typing

__author__ = "johntobin@johntobin.ie (John Tobin)"


SentinelMap = typing.Dict[str, int]

class Error(Exception):
  """Base class for exceptions."""
  pass


class ParsedSentinels(typing.NamedTuple(
    'ParsedSentinels',
    [('timestamps', SentinelMap),
     ('sleeping_until', SentinelMap),
     ('max_allowed_delay', SentinelMap),
    ])):
  """Container for parsed sentinels.

  Attributes:
    timestamps: timestamps for most recent backups.
    sleeping_until: timestamps for when sleeping machines are due back.
    max_allowed_delay: max delay, in seconds, for backups from a machine.
  """
  SLEEPING_UNTIL = 'sleeping_until'
  MAX_ALLOWED_DELAY = 'max_allowed_delay'


def parse_sentinels(directory: str) -> ParsedSentinels:
  """Parse a directory of sentinels.

  Args:
    directory: str, directory containing sentinel files.
  Returns:
    ParsedSentinels.
  Raises:
    Error, if any of the file names or contents are invalid.
  """

  data = ParsedSentinels({}, {}, {})
  files = glob.glob(os.path.join(directory, '*'))
  with fileinput.FileInput(files) as finput:
    for line in finput:
      line = line.strip()
      filename = os.path.basename(finput.filename())
      parts = re.split(r'\.', filename)
      if len(parts) == 1:
        data.timestamps[parts[0]] = int(line)
      elif len(parts) == 2 and parts[1] == ParsedSentinels.SLEEPING_UNTIL:
        data.sleeping_until[parts[0]] = int(line)
      elif len(parts) == 2 and parts[1] == ParsedSentinels.MAX_ALLOWED_DELAY:
        data.max_allowed_delay[parts[0]] = int(line)
      else:
        raise Error('Bad format in %s: %s, parts: %s' % (filename, line, parts))
  return data


def main(argv):
  if len(argv) != 2:
    raise Error('Usage: %s DIRECTORY' % argv[0])
  #  sentinels = parse_sentinels(argv[1])
