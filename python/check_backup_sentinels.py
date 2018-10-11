#!/usr/bin/env python3

"""%(prog)s [OPTIONS] DIRECTORY

Check sentinel times for all files in DIRECTORY.

Files in DIRECTORY:
  - HOSTNAME: the sentinel file for HOSTNAME.  Contains seconds since the epoch.
  - HOSTNAME.sleeping_until: when is HOSTNAME expected to wake up, e.g. while
    we're travelling and a laptop is at home.  Contains seconds since the epoch.
  - HOSTNAME.max_allowed_delay: max delay, in seconds, for backups from
    HOSTNAME.  Contains a number of seconds.
TODO: write more.
"""

import fileinput
import glob
import os
import re
import sys
import time
import typing

__author__ = "johntobin@johntobin.ie (John Tobin)"


# Type annotation aliases.
SentinelMap = typing.Dict[str, int]
Messages = typing.List[str]
Warnings = typing.List[str]

# Filename contents.
SLEEPING_UNTIL = 'sleeping_until'
MAX_ALLOWED_DELAY = 'max_allowed_delay'


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


def parse_sentinels(directory: str, default_delay: int) -> ParsedSentinels:
  """Parse a directory of sentinels.

  Args:
    directory: directory containing sentinel files.
    default_delay: default delay allowed if not explicitly configured.
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
      elif len(parts) == 2 and parts[1] == SLEEPING_UNTIL:
        data.sleeping_until[parts[0]] = int(line)
      elif len(parts) == 2 and parts[1] == MAX_ALLOWED_DELAY:
        data.max_allowed_delay[parts[0]] = int(line)
      else:
        raise Error('Bad format in %s: %s, parts: %s' % (filename, line, parts))

  for hostname in data.timestamps:
    if hostname not in data.max_allowed_delay:
      data.max_allowed_delay[hostname] = default_delay
    if hostname not in data.sleeping_until:
      data.sleeping_until[hostname] = 0

  return data


def check_sentinels(sentinels: ParsedSentinels,
                    max_global_delay: int) -> typing.Tuple[Warnings, Messages]:
  """Check sentinels for backups that are too old and return warnings.

  Args:
    sentinels: sentinels to check.
    max_global_delay: if every backup is older than this many seconds then
                      something is wrong, produce an error message.
  Returns:
    A tuple containing 1) warnings to output and 2) all generated messages for
    debugging purposes.
  """
  warnings = []
  messages = []  # type: typing.List[str]
  now = int(time.time())
  message = ('Backup for "%(host)s" too old:'
             ' current time %(now)d/%(now_human)s;'
             ' last backup %(last_backup)d/%(last_backup_human)s;'
             ' max allowed delay: %(max_delay)d/%(max_delay_human)s;'
             ' sleeping until: %(sleeping_until)d/%(sleeping_until_human)s')
  time_fmt = '%Y-%m-%d %H:%M'

  if not sentinels.timestamps:
    warnings.append('Zero sentinels passed, something is wrong.')
    messages.append(warnings[-1])
    return (warnings, messages)

  globally_delayed = [host for host in sentinels.timestamps
                      if now - sentinels.timestamps[host] > max_global_delay]
  if len(globally_delayed) == len(sentinels.timestamps):
    warnings.append('All backups are delayed by at least %d seconds'
                    % max_global_delay)
    messages.append(warnings[-1])

  for (host, last_backup) in sentinels.timestamps.items():
    max_delay = sentinels.max_allowed_delay[host]
    sleeping_until = sentinels.sleeping_until[host]
    warning = message % {
        'host': host,
        'now': now,
        'now_human': time.strftime(time_fmt, time.gmtime(now)),
        'last_backup': last_backup,
        'last_backup_human': time.strftime(time_fmt, time.gmtime(last_backup)),
        'max_delay': max_delay,
        'max_delay_human': time.strftime(time_fmt, time.gmtime(max_delay)),
        'sleeping_until': sleeping_until,
        'sleeping_until_human': time.strftime(time_fmt,
                                              time.gmtime(sleeping_until)),
    }
    messages.append(warning)

    if now - last_backup < max_delay:
      # Recent backup, all is well.
      continue
    if sleeping_until + max_delay > now:
      # Backup not due yet.
      continue

    # Something is wrong :(
    warnings.append(warning)

  messages = [message.replace('too old', 'debug info') for message in messages]
  return (warnings, messages)


def main(argv):
  if len(argv) != 2 or not os.path.isdir(argv[1]):
    raise Error('Usage: %s DIRECTORY' % argv[0])
  day = 24 * 60 * 60
  sentinels = parse_sentinels(argv[1], day)
  (warnings, messages) = check_sentinels(sentinels, day)
  if sys.stdin.isatty():
    for line in messages:
      print(line)
  for line in warnings:
    print(line, file=sys.stderr)
  if warnings:
    sys.exit(1)
  else:
    sys.exit(0)


if __name__ == '__main__':
  main(sys.argv)