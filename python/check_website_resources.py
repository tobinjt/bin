#!/usr/bin/env python3

"""%(prog)s JSON_CONFIG_FILE [JSON_CONFIG_FILE2...]

Check that the correct resources are returned for specific pages on a website,
to guard against bloating.  JSON_CONFIG_FILE specifies the URLs and resources.

JSON_CONFIG_FILE must contain a single list of dicts, where each dict has keys
"url" and "resources" with respective values being a string URL to check and a
list of string resource URLs.  Each dict can optionally have a "cookies" key
whose value is a dict mapping cookie names to values.

Example JSON_CONFIG_FILE:

  [
    {
      "url": "https://example.com/",
      "resources": [
        "https://example.com/javascript.js"
        "https://example.com/style.css",
      ]
    },
    {
      "url": "https://www.example.com/",
      "resources": [
        "https://www.example.com/javascript.js"
        "https://www.example.com/style.css",
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
from typing import Dict, List, NamedTuple, Text
import urllib.parse

__author__ = "johntobin@johntobin.ie (John Tobin)"

COOKIES_FILE = 'cookies.txt'
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
    cookies: cookies to send with request
  """
  url: Text
  resources: List[Text]
  cookies: Dict[Text, Text]


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


def write_cookies_file(lines: List[Text]):
  """Write cookies.txt.

  See read_wget_log() for why this function exists.

  Args:
    A list of lines to write.
  """
  with open(COOKIES_FILE, 'w') as cookies_txt:
    print('\n'.join(lines), file=cookies_txt)


def run_wget(url: Text, load_cookies: bool) -> List[Text]:
  """Run wget to fetch the specified URL, returning the contents of wget.log.

  Args:
    url: the URL to check.
    load_cookies: if True, add --load-cookies=cookies.txt to wget args.

  Returns:
    The contents of wget.log, or an empty list if running wget failed.
  """
  try:
    args = WGET_ARGS.copy()
    if load_cookies:
      args.append('--load-cookies=cookies.txt')
    args.append(url)
    subprocess.run(args, check=True, capture_output=True)
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


def check_single_url(config: SingleURLConfig) -> List[Text]:
  """Check a single URL requires only the expected resources.

  Args:
    config: a SingleURLConfig.

  Returns:
    A list of error messages.
  """
  log_lines = run_wget(config.url, False)
  if not log_lines:
    return ['Running wget failed']

  actual_resources = []
  for line in log_lines:
    if line.startswith('--'):
      actual_resources.append(line.split(' ')[-1])
  actual_resources = reverse_pagespeed_mangling(actual_resources)
  actual_resources.sort()
  logging.info('Actual resources for %s: %s', config.url, actual_resources)

  config.resources.sort()
  logging.info('Expected resources for %s: %s', config.url, config.resources)
  diff_generator = difflib.unified_diff(
      config.resources, actual_resources,
      fromfile='expected', tofile='actual')
  diffs = [d.rstrip('\n') for d in diff_generator]
  if not diffs:
    return []
  errors = ['Unexpected resource diffs for %s:' % config.url]
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
      cookies = host.get('cookies', {})
      if url not in resources:
        # The URL needs to be included, but do that automatically for the user.
        resources.insert(0, url)
      config.append(SingleURLConfig(url=url, resources=resources,
                                    cookies=cookies))
    return config


def generate_cookies_file_contents(url: Text, cookies: Dict[Text, Text]
                                   ) -> List[Text]:
  """Generate the contents of a cookies file.

  It would be much cleaner to use http.cookiejar for this, but after spending
  ~three hours on that approach I gave up, it's not suitable for standalone use.

  Args:
    url: the URL being processed; the hostname will be extracted from it.
    cookies: the cookies to include.
  Returns:
    A list of lines for the file.
  """
  lines = ['# Netscape HTTP Cookie File']
  host = urllib.parse.urlparse(url).hostname
  if host is None:
    raise ValueError('Unable to extract hostname from URL %s' % url)
  for key, value in cookies.items():
    # www.arianetobin.ie	FALSE	/	FALSE	1617567351	viewed_cookie_policy	yes
    lines.append('%s\tFALSE\t/\tFALSE\t0\t%s\t%s' % (host, key, value))
  return lines


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
      'config_files', nargs='*', metavar='JSON_CONFIG_FILE',
      help=('Config file specifying URLs and expected resources (multiple'
            ' files are supported but are completely independent)'))
  return argv_parser.parse_args(argv)


def main(argv: List[Text]) -> int:
  """Main."""
  options = parse_arguments(argv[1:])
  # On MacOS wget is in /usr/local/bin which is not in the default PATH cron
  # passes to child processes.
  os.environ['PATH'] += ':/usr/local/bin'
  messages = []
  host_configs = []
  for filename in options.config_files:
    host_configs.extend(read_config(filename))
  cwd_fd = os.open(os.curdir, os.O_DIRECTORY)

  # This will create temporary directories during tests but that's OK.
  with tempfile.TemporaryDirectory() as tmp_dir_name:
    os.chdir(tmp_dir_name)
    for host in host_configs:
      messages.extend(check_single_url(host))
    os.chdir(cwd_fd)
  if messages:
    print('\n'.join(messages), file=sys.stderr)
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
