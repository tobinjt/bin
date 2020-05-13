#!/usr/bin/env python3

"""%(prog)s JSON_CONFIG_FILE

Check that the correct resources are returned for specific pages on a website,
to guard against bloating.  JSON_CONFIG_FILE specifies the URLs and resources.

JSON_CONFIG_FILE must contain a single list of dicts, where each dict has keys
"url" and "resources" with respective values being a string URL to check and a
list of string resource URLs.

Example JSON_CONFIG_FILE:

  [
    {
      "url": "https://example.com/",
      "resources": [
        "https://example.com/javascript.js"
        "https://example.com/style.css",
      ]
    }
  ]
"""

import argparse
import difflib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from typing import List, NamedTuple, Text

__author__ = "johntobin@johntobin.ie (John Tobin)"

WGET_LOG = 'wget.log'
WGET_ARGS = [
    'wget',
    '--output-file=' + WGET_LOG,
    '--execute=robots=off',
    '--content-on-error',
    '--page-requisites',
    ]


class SingleURLConfig(NamedTuple):
  """Config for a single URL.

  Attributes:
    url: URL to check.
    resources: expected resources
  """
  url: Text
  resources: List[Text]


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
    A list of log lines with newlines stripped.
  """
  with open(WGET_LOG, 'r') as wget_log:
    return [line.rstrip('\n') for line in wget_log.readlines()]


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


def reverse_pagespeed_mangling(paths: List[Text]) -> List[Text]:
  """Reverse the changes made to paths by mod_pagespeed.

  This is based on reverse engineering the paths returned on Ariane's website,
  it's not complete or accurate.

  Args:
    paths: a list of paths.
  Returns:
    A list of paths; mangled paths will be reversed, unmangled paths will be
    unchanged.
  """
  new_paths = []
  replacements = {
      # foo/bar.css is rewritten to foo/A.bar.css.pagespeed...
      '.css': r'^A\.',
      # foo/bar.png is rewritten to foo/xbar.png.pagespeed...
      '.png': r'^x',
      }
  for path in paths:
    path = re.sub(r'(css|jpg|js|png)\.pagespeed\...\..*\.\1$', r'\1', path)
    for extension, regex in replacements.items():
      if path.endswith(extension):
        directory, filename = os.path.split(path)
        filename = re.sub(regex, '', filename)
        path = os.path.join(directory, filename)
    new_paths.append(path)
  return new_paths


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
  actual_resources = reverse_pagespeed_mangling(actual_resources)
  actual_resources.sort()
  logging.info('Actual resources for %s: %s', url, actual_resources)

  expected_resources.sort()
  logging.info('Expected resources for %s: %s', url, expected_resources)
  diff_generator = difflib.unified_diff(
      expected_resources, actual_resources,
      fromfile='expected', tofile='actual')
  diffs = [d.rstrip('\n') for d in diff_generator]
  if not diffs:
    return []
  errors = ['Unexpected resource diffs for %s:' % url]
  return errors + diffs


def read_config(path: Text) -> List[SingleURLConfig]:
  """Read the specified config and parse it as JSON.

  Args:
    path: path to the file to read.
  Returns:
    List of SingleURLConfig.
  """
  with open(path, 'r') as filehandle:
    data = json.loads(filehandle.read())
    config = []
    for host in data:
      # TODO: validate the config.
      url = host['url']
      resources = host['resources']
      if url not in resources:
        # The URL needs to be included, but do that automatically for the user.
        resources.insert(0, url)
      config.append(SingleURLConfig(url=url, resources=resources))
    return config


def parse_arguments(argv: List[Text]) -> argparse.Namespace:
  """Parse command line arguments.

  Args:
    argv: the arguments to parse.
  Returns:
    argparse.Namespace, with attributes set based on the arguments.
  """
  description = '\n'.join(__doc__.split('\n')[1:])
  usage = __doc__.split('\n')[0]

  argv_parser = argparse.ArgumentParser(
      description=description, usage=usage,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  argv_parser.add_argument(
      'config', metavar='JSON_CONFIG_FILE',
      help='Config file specifying URLs and expected resources')
  return argv_parser.parse_args(argv)


def main(argv: List[Text]) -> int:
  """Main."""
  options = parse_arguments(argv[1:])
  config = read_config(options.config)
  messages = []
  cwd_fd = os.open(os.curdir, os.O_DIRECTORY)
  # This will create temporary directories during tests but that's OK.
  with tempfile.TemporaryDirectory() as tmp_dir_name:
    os.chdir(tmp_dir_name)
    for host in config:
      messages.extend(check_single_url(host.url, host.resources))
    os.chdir(cwd_fd)
  if messages:
    print('\n'.join(messages), file=sys.stderr)
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
