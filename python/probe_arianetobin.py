#!/usr/bin/env python3

"""
This script probes a website to check if it's up and running by looking for a
specific sentinel string in the page content. It will attempt this multiple
times before giving up.
"""

import logging
import sys
import urllib.error
import urllib.request

import retry

NUMBER_OF_ATTEMPTS = 5
SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS = 60
SENTINEL = "<title>Ariane Tobin Jewellery - Ariane Tobin Jewellery</title>"
WEBSITE = "https://www.arianetobin.ie/"


class SentinelNotFoundError(Exception):
    """Custom exception raised when the sentinel string is not found in the page."""


@retry.retry(
    (urllib.error.URLError, urllib.error.HTTPError, SentinelNotFoundError),
    tries=NUMBER_OF_ATTEMPTS,
    delay=SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS,
)
def probe_website(website: str, sentinel: str) -> None:
    """
    Probes the website to see if it's up and the sentinel is present.
    The @retry decorator handles the retry logic.
    """
    with urllib.request.urlopen(website, timeout=30) as response:
        # Read and decode the content
        # The 'ignore' errors handler will drop any characters that
        # can't be decoded, which is a reasonable fallback.
        content = response.read().decode("utf-8", errors="ignore")

        if sentinel not in content:
            # Raise an exception to trigger a retry
            raise SentinelNotFoundError(
                f"Sentinel '{sentinel}' not found in the response."
            )


def main():
    """
    Tries multiple times to fetch a website and check for a sentinel string.
    """
    try:
        probe_website(WEBSITE, SENTINEL)
        return 0
    except (urllib.error.URLError, urllib.error.HTTPError, SentinelNotFoundError) as e:
        print(
            f"Did not find sentinel '{SENTINEL}' in {WEBSITE} after {
                NUMBER_OF_ATTEMPTS
            } attempts.",
            file=sys.stderr,
        )
        print(f"Final error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig()
    sys.exit(main())
