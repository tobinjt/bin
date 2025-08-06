#!/usr/bin/env python3

"""Checks that various domains redirect to a canonical URL."""

import logging
import sys

import requests
import retry


logger = logging.getLogger("check_redirects_for_hosting")


class Error(Exception):
    """Base class for errors."""


class MissingRedirectError(Error):
    """Expected redirect not found."""


@retry.retry(MissingRedirectError, tries=5, delay=1)
def check_single_redirect(expected_url: str, check_url: str) -> None:
    """
    Checks that a single URL redirects to the expected URL.
    Retries 5 times. Raises a MissingRedirectError if the redirect isn't found.

    Args:
        expected_url: The URL we expect to be redirected to.
        check_url: The URL to check for redirection.
    """
    logger.info(f"checking {check_url}")
    req = requests.head(check_url, allow_redirects=True)
    if req.url != expected_url:
        logger.warning(
            f"bad redirect for {check_url}: {req.url}, expected {expected_url}"
        )
        raise MissingRedirectError(f"URL {check_url} did not redirect.")


def check_redirects(expected_url: str, *urls: str) -> list[str]:
    """
    Checks a list of URLs for correct redirection.
    Returns a list of error messages for failures.

    Args:
        expected_url: The URL we expect to be redirected to.
        urls: The URLs to check for redirection.
    """
    error_messages = []
    for url in urls:
        try:
            check_single_redirect(expected_url, url)
        except MissingRedirectError as e:
            error_messages.append(str(e))
    return error_messages


def main() -> int:
    """Main function."""
    error_messages = check_redirects(
        "https://www.arianetobin.ie/",
        "http://ariane.ie/",
        "https://ariane.ie/",
        "http://www.ariane.ie/",
        "https://www.ariane.ie/",
        "http://arianetobin.ie/",
        "https://arianetobin.ie/",
        "http://arianetobin.com/",
        "https://arianetobin.com/",
        "http://www.arianetobin.com/",
        "https://www.arianetobin.com/",
        "http://metalatplay.com/",
        "https://metalatplay.com/",
        "http://www.metalatplay.com/",
        "https://www.metalatplay.com/",
        "http://metalatwork.com/",
        "https://metalatwork.com/",
        "http://www.metalatwork.com/",
        "https://www.metalatwork.com/",
        "http://nakedmetalsmith.com/",
        "https://nakedmetalsmith.com/",
        "http://www.nakedmetalsmith.com/",
        "https://www.nakedmetalsmith.com/",
    )

    if error_messages:
        print(f"Total failures: {len(error_messages)}", file=sys.stderr)
        for failure in error_messages:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    sys.exit(main())
