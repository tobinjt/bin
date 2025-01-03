#!/usr/bin/env python3
"""%(prog)s JSON_CONFIG_FILE [JSON_CONFIG_FILE2...]

Check that the correct resources are returned for specific pages on a website,
to guard against bloating.  JSON_CONFIG_FILE specifies the URLs and resources.

JSON_CONFIG_FILE must contain a single list of dicts, each dict containing:
- url (required): the URL to check
- resources (required): list of expected resources for the URL.
- optional_resources (optional): list of optional resources for the URL.
- optional_resource_regexes (optional): list of optional resources regexes for
    the URL.
- cookies (optional): dict of cookie keys to cookie values to send when
    requesting the URL.
- comment (optional): a comment to display in messages to more easily identify
    which URL unexpected or missing resources are being reported for (e.g. when a
    URL is listed multiple times with different cookies).

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
            ],
            "optional_resource_regexes": [
                "https://www.example.com/bar.*.js",
            ]
        }
    ]
"""

import argparse
import json
import logging
import os

# This import works because virtualenv's python3 is the first python3 in $PATH.
import pydantic
import re
import subprocess
import sys
import tempfile
import urllib.parse

__author__ = "johntobin@johntobin.ie (John Tobin)"

# These constants are used consistently so mutating them doesn't provide signal.
COOKIES_FILE = "cookies.txt"  # pragma: no mutate
WGET_LOG = "wget.log"  # pragma: no mutate
WGET_ARGS = [  # pragma: no mutate
    "wget",  # pragma: no mutate
    "--output-file=" + WGET_LOG,  # pragma: no mutate
    "--execute=robots=off",  # pragma: no mutate
    "--content-on-error",  # pragma: no mutate
    "--page-requisites",  # pragma: no mutate
]


class Error(Exception):
    """Base class for exceptions."""


class WgetFailedException(Error):
    """Running wget failed."""


class SingleURLConfig(pydantic.BaseModel):
    """Config for a single URL.

    Attributes:
        url: URL to check.
        resources: expected resources
        optional_resources: optional resources
        optional_resource_regexes: optional resource regexes
        cookies: cookies to send with request
        comment: comment to help identify the config.
    """

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    url: str
    resources: list[str]
    comment: str = "no comment"
    cookies: dict[str, str] = {}
    optional_resources: list[str] = []
    optional_resource_regexes: list[str] = []


def read_wget_log() -> list[str]:
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
    with open(WGET_LOG, encoding="utf8") as wget_log:
        return [line.rstrip("\n") for line in wget_log.readlines()]  # pragma: no mutate


def write_cookies_file(*, lines: list[str]):
    """Write cookies.txt.

    See read_wget_log() for why this function exists.

    Args:
        A list of lines to write.
    """
    with open(COOKIES_FILE, "w", encoding="utf8") as cookies_txt:
        print("\n".join(lines), file=cookies_txt)


def run_wget(*, url: str, load_cookies: bool) -> list[str]:
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
        args.append("--load-cookies=cookies.txt")
    args.append(url)
    try:
        subprocess.run(args, check=True, capture_output=True)
        return read_wget_log()
    except subprocess.CalledProcessError as err:
        message = f"wget for {url} failed: {err.stderr}; {str(err)}"
        logging.error(message)
        raise WgetFailedException(message) from err


def reverse_pagespeed_mangling(*, paths: list[str]) -> list[str]:
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
        ".css": r"^A\.",
        # foo/bar.png is rewritten to foo/xbar.png.pagespeed...
        ".png": r"^x",
    }
    for path in paths:
        path = re.sub(r"(css|jpg|js|png)\.pagespeed\...\..*\.\1$", r"\1", path)
        for extension, regex in replacements.items():
            if path.endswith(extension):
                directory, filename = os.path.split(path)
                filename = re.sub(regex, "", filename)
                path = os.path.join(directory, filename)
        new_paths.append(path)
    return new_paths


def check_single_url(*, config: SingleURLConfig) -> list[str]:
    """Check a single URL requires only the expected resources.

    Args:
        config: a SingleURLConfig.

    Returns:
        A list of error messages.
    """
    if config.cookies:
        lines = generate_cookies_file_contents(url=config.url, cookies=config.cookies)
        write_cookies_file(lines=lines)
    try:
        log_lines = run_wget(url=config.url, load_cookies=bool(config.cookies))
    except WgetFailedException as err:
        return [f"{config.url} ({config.comment}): running wget failed; {str(err)}"]

    fetched_resources = set()
    for line in log_lines:
        if line.startswith("--"):
            fetched_resources.add(line.split(" ")[-1])
    actual_resources = reverse_pagespeed_mangling(paths=list(fetched_resources))
    # Strip out any optional_resources.
    actual_resources = list(set(actual_resources) - set(config.optional_resources))
    actual_resources.sort()
    # No tests for logging, perhaps I should add some?
    logging.info(
        "Actual resources for %s (%s): %s",  # pragma: no mutate
        config.url,
        config.comment,
        actual_resources,
    )
    config.resources.sort()
    logging.info(
        "Expected resources for %s (%s): %s",  # pragma: no mutate
        config.url,
        config.resources,
        config.comment,
    )

    errors = []
    missing_resources = set(config.resources) - set(actual_resources)
    if missing_resources:
        errors.append(f"Missing resources for {config.url} ({config.comment}):")
        errors.extend(sorted(missing_resources))

    extra_resources = set(actual_resources) - set(config.resources)
    extra_unmatched = []
    regexes = [re.compile(x) for x in config.optional_resource_regexes]
    for extra_resource in extra_resources:
        if all(regex.match(extra_resource) is None for regex in regexes):
            extra_unmatched.append(extra_resource)
    if extra_unmatched:
        errors.append(f"Unmatched resources for {config.url} ({config.comment}):")
        errors.extend(extra_unmatched)

    return errors


def read_config(*, path: str) -> list[SingleURLConfig]:
    """Read the specified config and parse it as JSON.

    Args:
        path: path to the file to read.
    Returns:
        List of SingleURLConfig.
    """
    with open(path, encoding="utf8") as filehandle:
        data = json.loads(filehandle.read())
    configs = []
    for config in data:
        # pydantic can perform the URL and resources checks, but the error messages are
        # far less clear, so for user-friendliness I implemented the checks here.
        if "url" not in config:
            raise ValueError(f'{path}: required config "url" not provided')
        if "resources" not in config:
            raise ValueError(f'{path}: required config "resources" not provided')
        if config["url"] not in config["resources"]:
            # The URL needs to be included, but do that automatically for the user.
            config["resources"].insert(0, config["url"])
        configs.append(SingleURLConfig(**config))
    return configs


def generate_cookies_file_contents(*, url: str, cookies: dict[str, str]) -> list[str]:
    """Generate the contents of a cookies file.

    It would be much cleaner to use http.cookiejar for this, but after spending
    ~three hours on that approach I gave up, it's not suitable for standalone use.

    Args:
        url: the URL being processed; the hostname will be extracted from it.
        cookies: the cookies to include.
    Returns:
        A list of lines for the file.
    """
    lines = ["# Netscape HTTP Cookie File"]
    host = urllib.parse.urlparse(url).hostname
    if host is None:
        raise ValueError(f"Unable to extract hostname from URL {url}")
    for key, value in cookies.items():
        # www.arianetobin.ie	FALSE	/	FALSE	1617567351	viewed_cookie_policy	yes
        lines.append(f"{host}\tFALSE\t/\tFALSE\t0\t{key}\t{value}")
    return lines


def parse_arguments(*, argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: the arguments to parse.
    Returns:
        argparse.Namespace, with attributes set based on the arguments.
    """
    (usage, description) = __doc__.split("\n", maxsplit=1)  # pragma: no mutate
    argv_parser = argparse.ArgumentParser(
        description=description,
        usage=usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    argv_parser.add_argument(
        "config_files",
        nargs="+",
        metavar="JSON_CONFIG_FILE",
        default=[],
        help=(
            "Config file specifying URLs and expected resources (multiple"
            " files are supported but are completely independent)"
        ),
    )
    return argv_parser.parse_args(argv)


def main(*, argv: list[str]) -> int:
    """Main."""
    options = parse_arguments(argv=argv[1:])
    messages = []
    host_configs = []
    for filename in options.config_files:
        host_configs.extend(read_config(path=filename))

    # This will create temporary directories during tests but that's OK.
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        os.chdir(tmp_dir_name)
        for host_config in host_configs:
            messages.extend(check_single_url(config=host_config))
    if messages:
        print("\n".join(messages), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no mutate
    sys.exit(main(argv=sys.argv))
