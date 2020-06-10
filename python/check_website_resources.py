#!/usr/bin/env python3

"""%(prog)s JSON_CONFIG_FILE [JSON_CONFIG_FILE2...]

Check that the correct resources are returned for specific pages on a website,
to guard against bloating.  JSON_CONFIG_FILE specifies the URLs and resources.

JSON_CONFIG_FILE must contain a single list of dicts, each dict containing:
- url (required): the URL to check
- resources (required): list of expected resources for the URL.
- cookies (optional): dict of cookie keys to cookie values to send when
  requesting the URL.
- comment (optional): a comment to display in messages to more easily identify
  which URL diffs are being reported on (e.g. when a URL is listed multiple
  times with different cookies).

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
      ],
      "cookies": {
        "cart_id": "13579"
      },
      "comment": "something useful",
      "optional_resources": [
        "https://www.example.com/foo.js",
      ]
    }
  ]
"""

import argparse
import dataclasses
import difflib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Text
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


class Error(Exception):
  """Base class for exceptions."""


class WgetFailedException(Error):
  """Running wget failed."""


@dataclasses.dataclass(frozen=True)
class SingleURLConfig:
  """Config for a single URL.

  Attributes:
    url: URL to check.
    resources: expected resources
    optional_resources: optional resources
    cookies: cookies to send with request
    comment: comment to help identify the config.
  """
  url: Text
  resources: List[Text]
  comment: Text
  cookies: Dict[Text, Text] = dataclasses.field(default_factory=dict)
  optional_resources: List[Text] = dataclasses.field(default_factory=list)


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
    The contents of wget.log.

  Raises:
    WgetFailedException if running wget failed.
  """
  args = WGET_ARGS.copy()
  if load_cookies:
    args.append('--load-cookies=cookies.txt')
  args.append(url)
  try:
    subprocess.run(args, check=True, capture_output=True)
    return read_wget_log()
  except subprocess.CalledProcessError as err:
    message = 'wget for %s failed: %s; %s' % (url, err.stderr, str(err))
    logging.error(message)
    raise WgetFailedException(message)


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
  if config.cookies:
    lines = generate_cookies_file_contents(config.url, config.cookies)
    write_cookies_file(lines)
  try:
    log_lines = run_wget(config.url, bool(config.cookies))
  except WgetFailedException as err:
    return ['%s (%s): running wget failed; %s'
            % (config.url, config.comment, str(err))]

  fetched_resources = set()
  for line in log_lines:
    if line.startswith('--'):
      fetched_resources.add(line.split(' ')[-1])
  actual_resources = reverse_pagespeed_mangling(list(fetched_resources))
  # Strip out any optional_resources.
  actual_resources = list(set(actual_resources)
                          - set(config.optional_resources))
  actual_resources.sort()
  logging.info('Actual resources for %s (%s): %s', config.url, config.comment,
               actual_resources)

  config.resources.sort()
  logging.info('Expected resources for %s (%s): %s', config.url,
               config.resources, config.comment)
  diff_generator = difflib.unified_diff(
      config.resources, actual_resources,
      fromfile='expected', tofile='actual')
  diffs = [d.rstrip('\n') for d in diff_generator]
  if not diffs:
    return []
  errors = ['Unexpected resource diffs for %s (%s):'
            % (config.url, config.comment)]
  return errors + diffs


def validate_list_of_strings(path: Text, name: Text, data: List[Text]):
  """Validate a data structure is a list of strings.

  Args:
    path: path to the config file, used in error messages.
    name: name of the data structure, used in error messages.
    data: the data structure to validate.
  Raises:
    ValueError if any validation fails.
  """
  if not isinstance(data, list):
    raise ValueError('%s: "%s" must be a list of strings' % (path, name))
  bad = [str(r) for r in data if not isinstance(r, str)]
  if bad:
    raise ValueError('%s: all "%s" must be strings: %s'
                     % (path, name, ', '.join(bad)))


def validate_dict_of_strings(path: Text, name: Text, data: List[Text]):
  """Validate a data structure is a dict of string -> string.

  Args:
    path: path to the config file, used in error messages.
    name: name of the data structure, used in error messages.
    data: the data structure to validate.
  Raises:
    ValueError if any validation fails.
  """
  if not isinstance(data, dict):
    raise ValueError('%s: "%s" must be a dict' % (path, name))
  contents = list(data.keys()) + list(data.values())
  bad = [str(c) for c in contents if not isinstance(c, str)]
  if bad:
    raise ValueError('%s: everything in "%s" must be strings: %s'
                     % (path, name, ', '.join(bad)))


def validate_user_config(path: Text, configs: Any):
  """Validate the configs supplied by the user.

  NOTE: the configs will be modified in-place to fill missing fields with
  defaults.

  Args:
    path: path of the config file, used for error messages.
    configs: the data structure returned by json.loads().
  Raises:
    ValueError if any validation fails.
  """
  if not isinstance(configs, list):
    raise ValueError('%s: Top-level data structure must be a list' % path)
  for config in configs:
    if not isinstance(config, dict):
      raise ValueError('%s: All entries in the list must be dicts' % path)
    known_keys = set(['url', 'resources', 'cookies', 'comment',
                      'optional_resources'])
    actual_keys = set(config.keys())
    if not actual_keys.issubset(known_keys):
      bad_keys = ', '.join(list(actual_keys - known_keys))
      raise ValueError('%s: Unsupported key(s): %s' % (path, bad_keys))
    if 'url' not in config:
      raise ValueError('%s: required config "url" not provided' % path)
    if 'resources' not in config:
      raise ValueError('%s: required config "resources" not provided' % path)
    if 'cookies' not in config:
      config['cookies'] = {}
    if 'comment' not in config:
      config['comment'] = config['url']
    if 'optional_resources' not in config:
      config['optional_resources'] = []

    if not isinstance(config['url'], str):
      raise ValueError('%s: url must be a string' % path)

    if not isinstance(config['comment'], str):
      raise ValueError('%s: comment must be a string' % path)

    validate_list_of_strings(path, 'resources', config['resources'])
    validate_list_of_strings(path, 'optional_resources',
                             config['optional_resources'])
    validate_dict_of_strings(path, 'cookies', config['cookies'])



def read_config(path: Text) -> List[SingleURLConfig]:
  """Read the specified config and parse it as JSON.

  Args:
    path: path to the file to read.
  Returns:
    List of SingleURLConfig.
  """
  with open(path, 'r') as filehandle:
    data = json.loads(filehandle.read())
  validate_user_config(path, data)
  configs = []
  for config in data:
    if config['url'] not in config['resources']:
      # The URL needs to be included, but do that automatically for the user.
      config['resources'].insert(0, config['url'])
    configs.append(SingleURLConfig(**config))
  return configs


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
