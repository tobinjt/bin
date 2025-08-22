#!/usr/bin/env python3

"""Check DNS records for hosts."""

import dataclasses
import logging
import sys

import dns.exception
import dns.resolver
import retry

logger = logging.getLogger("check_dns_for_hosting")

# --- Configuration ---

SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS = 60
NUMBER_OF_ATTEMPTS = 5

# IP Addresses
HETZNER_IPV4 = ["168.119.99.114"]
HETZNER_IPV6 = ["2a01:4f8:c010:21a::1"]
GITHUB_PAGES_IPV4 = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
]
GITHUB_PAGES_IPV6 = [
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
]

# MX Records
GOOGLE_MX_RECORDS = [
    "1 aspmx.l.google.com.",
    "10 aspmx2.googlemail.com.",
    "10 aspmx3.googlemail.com.",
    "5 alt1.aspmx.l.google.com.",
    "5 alt2.aspmx.l.google.com.",
]


@dataclasses.dataclass
class HostConfig:
    """Configuration for a host to be checked."""

    name: str
    ipv4: list[str]
    ipv6: list[str]
    mx: list[str] | None = None
    check_www: bool = False


# Host Configuration
HOSTS_TO_CHECK = [
    HostConfig(
        name="ariane.ie",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="arianetobin.com",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="arianetobin.ie",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="dev.arianetobin.ie",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
    ),
    HostConfig(
        name="test.arianetobin.ie",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
    ),
    HostConfig(
        name="johntobin.ie",
        ipv4=GITHUB_PAGES_IPV4,
        ipv6=GITHUB_PAGES_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="metalatplay.com",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="metalatwork.com",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
    HostConfig(
        name="nakedmetalsmith.com",
        ipv4=HETZNER_IPV4,
        ipv6=HETZNER_IPV6,
        mx=GOOGLE_MX_RECORDS,
        check_www=True,
    ),
]


@retry.retry(
    (dns.resolver.NoNameservers, dns.exception.Timeout),
    tries=NUMBER_OF_ATTEMPTS,
    delay=SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS,
)
def query_dns_with_retry(hostname: str, atype: str) -> dns.resolver.Answer:
    """
    Query DNS, retrying on failure, and return the answer.

    Retries up to NUMBER_OF_ATTEMPTS times on timeout.

    Args:
        hostname: The hostname to query.
        atype: The DNS record type to query (e.g., "A", "AAAA", "MX").

    Returns:
        A dns.resolver.Answer object on success.

    Raises:
        dns.exception.Timeout if all retries fail.
    """
    logger.info(f"looking up {atype} for {hostname}")
    return dns.resolver.resolve(hostname, atype)


def query_dns(hostname: str, atype: str) -> dns.resolver.Answer | None:
    """
    Query DNS, returning None on failures .

    Args:
        hostname: The hostname to query.
        atype: The DNS record type to query (e.g., "A", "AAAA", "MX").

    Returns:
        A dns.resolver.Answer object on success, or None on failure.
        Retries up to NUMBER_OF_ATTEMPTS times on timeout.
    """
    try:
        return query_dns_with_retry(hostname, atype)
    except dns.exception.Timeout as e:
        logger.warning(f"lookup of {atype} for {hostname} failed with {e}")
        return None


def check_dns_for_host(hostname: str, addresses: list[str], record_type: str) -> bool:
    """
    Check A|AAAA records for a host.

    Args:
        hostname: The hostname to check.
        addresses: The expected addresses.
        record_type: A|AAAA.

    Returns:
        True if the A|AAAA record is correct, False otherwise.
    """
    answers = query_dns(hostname, record_type)
    if not answers:
        logger.warning(f"Bad {record_type} record for {hostname}: No answer from DNS.")
        return False

    records = {a.to_text() for a in answers}
    expected = set(addresses)
    if expected != records:
        logger.warning(
            f"Bad {record_type} record for {hostname}: "
            f"Expected {expected}. "
            f"Got: {records}"
        )
        return False
    return True


def check_mx_for_host(hostname: str, expected_mx_records: list[str]) -> bool:
    """
    Checks MX records for a host.

    Args:
        hostname: The hostname to check.
        expected_mx_records: A list of expected MX records in "priority name" format.

    Returns:
        True if all expected MX records are found, False otherwise.
    """
    mx_answers = query_dns(hostname, "MX")
    if mx_answers and mx_answers.rrset:
        found_mx_records = {f"{mx.preference} {mx.exchange}" for mx in mx_answers.rrset}
    else:
        found_mx_records = set([])
    expected_set = set(expected_mx_records)

    if expected_set != found_mx_records:
        logger.warning(
            f"Error: Bad MX records for {hostname}: "
            f"Expected {expected_set}. "
            f"Got {found_mx_records}"
        )
        return False
    return True


def check_single_host(host_config: HostConfig) -> bool:
    """Performs all the checks for a single host.

    Args:
        host_config: config for the host to check.

    Returns:
        bool, whether all checks passed.
    """
    hostname = host_config.name
    logger.info(f"--- Checking {hostname} ---")

    all_checks_ok = check_dns_for_host(hostname, host_config.ipv4, "A")
    all_checks_ok = (
        check_dns_for_host(hostname, host_config.ipv6, "AAAA") and all_checks_ok
    )

    if host_config.check_www:
        logger.info(f"--- Checking www.{hostname} ---")
        all_checks_ok = (
            check_dns_for_host(f"www.{hostname}", host_config.ipv4, "A")
            and all_checks_ok
        )
        all_checks_ok = (
            check_dns_for_host(f"www.{hostname}", host_config.ipv6, "AAAA")
            and all_checks_ok
        )

    if host_config.mx:
        logger.info(f"--- Checking MX records for {hostname} ---")
        all_checks_ok = check_mx_for_host(hostname, host_config.mx) and all_checks_ok

    return all_checks_ok


def main(argv: list[str]) -> int:
    """
    Checks DNS records for a predefined list of hosts.

    Args:
        argv: Command-line arguments, including the script name.

    Returns:
        0 if all checks pass, 1 otherwise.
    """
    if len(argv) > 1:
        logger.warning(f"Usage: {argv[0]}")
        logger.warning(f"Unexpected arguments: {' '.join(argv[1:])}")
        return 1

    all_checks_ok = True
    for host_config in HOSTS_TO_CHECK:
        all_checks_ok = check_single_host(host_config) and all_checks_ok

    if all_checks_ok:
        logger.info("\nAll DNS checks passed.")
        return 0

    logger.warning("\nSome DNS checks failed.")
    return 1


if __name__ == "__main__":
    if sys.stdin.isatty():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    sys.exit(main(sys.argv))
