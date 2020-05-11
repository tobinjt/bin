#!/usr/bin/env python3

"""%(prog)s

Check that the correct resources are returned for specific pages on a website,
to guard against bloating.
"""

import difflib
import logging
#  import re
import subprocess
from typing import List, Text

__author__ = "johntobin@johntobin.ie (John Tobin)"

WGET_LOG = 'wget.log'
WGET_ARGS = [
    'wget',
    '--output-file=' + WGET_LOG,
    '--execute=robots=off',
    '--content-on-error',
    '--page-requisites',
    ]


def read_wget_log() -> List[Text]:
  """Read and return wget.log.

  Inlining this code and using pyfakefs breaks pytest, it fails with:
  <stacktrace>
  sqlite3.OperationalError: table coverage_schema already exists
  During handling of the above exception, another exception occurred:
  <stacktrace>
  OSError: [Errno 9] Bad file descriptor in the fake filesystem: '5'
  During handling of the above exception, another exception occurred:
  <stacktrace>
  ValueError: was already stopped

  Returns:
    A list of log lines.
  """
  with open(WGET_LOG, 'r') as wget_log:
    return wget_log.readlines()


def run_wget(url: Text) -> List[Text]:
  """Run wget to fetch the specified URL, returning the contents of wget.log.

  Args:
    url: the URL to check.

  Returns:
    The contents of wget.log, or an empty list if running wget failed.
  """
  try:
    subprocess.run(WGET_ARGS + [url], check=True, capture_output=True)
    return read_wget_log()
  except subprocess.CalledProcessError as err:
    logging.error('wget for %s failed: %s', url, err.stderr)
    return []


def check_single_url(url: Text, expected_resources: List[Text]) -> List[Text]:
  """Check a single URL requires only the expected resources.

  Args:
    url: the URL to check.
    expected_resources: the expected resources.

  Returns:
    A list of error messages.
  """
  log_lines = run_wget(url)
  if not log_lines:
    return ['Running wget failed']

  actual_resources = []
  for line in log_lines:
    if line.startswith('--'):
      actual_resources.append(line.split(' ')[-1])
  actual_resources.sort()

  expected_resources.sort()
  diff_generator = difflib.unified_diff(
      expected_resources, actual_resources,
      fromfile='expected', tofile='actual')
  diffs = [d.rstrip('\n') for d in diff_generator]
  if not diffs:
    return []
  errors = ['Unexpected resource diffs for %s:' % url]
  return errors + diffs
