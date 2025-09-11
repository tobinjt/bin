import logging
import time
import unittest
from typing import override
from unittest import mock

import check_dns_for_hosting
import dns.exception
import dns.resolver
import dns.name


class MockRdata:
    """A mock for dns.rdata.Rdata."""

    def __init__(self, text: str):
        self._text: str = text

    def to_text(self):
        """Returns the text form of the rdata."""
        return self._text


class MockMxRdata:
    """A mock for MX rdata."""

    def __init__(self, preference: int, exchange: str):
        self.preference: int = preference
        self.exchange: dns.name.Name = dns.name.from_text(exchange)

    @override
    def __str__(self):
        return f"{self.preference} {self.exchange}"


class MockAnswer:
    """A mock for dns.resolver.Answer."""

    def __init__(self, records: list[MockMxRdata | MockRdata]):
        self._records: list[MockMxRdata | MockRdata] = records

    def __iter__(self):
        return iter(self._records)

    @property
    def rrset(self):
        """Returns the mocked rrset."""
        return self


class TestQueryDns(unittest.TestCase):
    """Test cases for query_dns."""

    @mock.patch.object(check_dns_for_hosting, "query_dns_with_retry")
    def test_success(self, mock_retry_func: mock.Mock):
        """Test that query_dns returns the answer on success."""
        expected = "the answer"
        mock_retry_func.return_value = expected
        result = check_dns_for_hosting.query_dns("example.com", "A")
        self.assertEqual(result, expected)
        mock_retry_func.assert_called_once_with("example.com", "A")

    @mock.patch.object(check_dns_for_hosting, "query_dns_with_retry")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_timeout(self, mock_logger: mock.Mock, mock_retry_func: mock.Mock):
        """Test that query_dns returns None on timeout."""
        mock_retry_func.side_effect = dns.exception.Timeout
        result = check_dns_for_hosting.query_dns("example.com", "A")
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()


class TestQueryDnsWithRetry(unittest.TestCase):
    """Test cases for query_dns_with_retry."""

    @mock.patch.object(dns.resolver, "resolve")
    def test_success_on_first_try(self, mock_resolve: mock.Mock):
        """Test that query_dns_with_retry returns the answer on the first attempt."""
        expected = "the answer"
        mock_resolve.return_value = expected
        result = check_dns_for_hosting.query_dns_with_retry("example.com", "A")
        self.assertEqual(result, expected)
        mock_resolve.assert_called_once_with("example.com", "A")

    @mock.patch.object(time, "sleep")
    @mock.patch.object(dns.resolver, "resolve")
    def test_success_after_retries(
        self, mock_resolve: mock.Mock, mock_sleep: mock.Mock
    ):
        """Test that query_dns_with_retry succeeds after some retries on Timeout."""
        expected = "the answer"
        # Fail twice, then succeed.
        mock_resolve.side_effect = [
            dns.exception.Timeout,
            dns.resolver.NoNameservers,
            expected,
        ]

        result = check_dns_for_hosting.query_dns_with_retry("example.com", "A")
        self.assertEqual(result, expected)
        self.assertEqual(mock_resolve.call_count, 3)
        # It sleeps between retries.
        self.assertEqual(mock_sleep.call_count, 2)
        mock_resolve.assert_has_calls(
            [
                mock.call("example.com", "A"),
                mock.call("example.com", "A"),
                mock.call("example.com", "A"),
            ]
        )

    @mock.patch.object(time, "sleep")
    @mock.patch.object(dns.resolver, "resolve")
    def test_failure_after_all_retries(
        self, mock_resolve: mock.Mock, mock_sleep: mock.Mock
    ):
        """Test that query_dns_with_retry fails after all retries on Timeout."""
        mock_resolve.side_effect = dns.exception.Timeout

        with self.assertRaises(dns.exception.Timeout):
            check_dns_for_hosting.query_dns_with_retry("example.com", "A")

        self.assertEqual(
            mock_resolve.call_count, check_dns_for_hosting.NUMBER_OF_ATTEMPTS
        )
        self.assertEqual(
            mock_sleep.call_count, check_dns_for_hosting.NUMBER_OF_ATTEMPTS - 1
        )

    @mock.patch.object(dns.resolver, "resolve")
    def test_immediate_failure_on_other_exception(self, mock_resolve: mock.Mock):
        """Test that query_dns_with_retry fails immediately for non-timeout errors."""
        mock_resolve.side_effect = dns.resolver.NXDOMAIN
        with self.assertRaises(dns.resolver.NXDOMAIN):
            check_dns_for_hosting.query_dns_with_retry("example.com", "A")
        mock_resolve.assert_called_once_with("example.com", "A")


class TestCheckDnsForHost(unittest.TestCase):
    """Test cases for check_dns_for_host."""

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    def test_success(self, mock_query_dns: mock.Mock):
        """Test success case with correct records."""
        mock_query_dns.return_value = MockAnswer(
            [MockRdata("1.2.3.4"), MockRdata("5.6.7.8")]
        )
        self.assertTrue(
            check_dns_for_hosting.check_dns_for_host(
                "good.com", ["1.2.3.4", "5.6.7.8"], "A"
            )
        )
        mock_query_dns.assert_called_once_with("good.com", "A")

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_failure_no_answer(self, mock_logger: mock.Mock, mock_query_dns: mock.Mock):
        """Test failure when there is no DNS answer."""
        mock_query_dns.return_value = None
        self.assertFalse(
            check_dns_for_hosting.check_dns_for_host("bad.com", ["1.2.3.4"], "A")
        )
        mock_logger.warning.assert_called_once_with(
            "Bad A record for bad.com: No answer from DNS."
        )

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_failure_wrong_records(
        self, mock_logger: mock.Mock, mock_query_dns: mock.Mock
    ):
        """Test failure when DNS returns incorrect records."""
        mock_query_dns.return_value = MockAnswer([MockRdata("9.9.9.9")])
        self.assertFalse(
            check_dns_for_hosting.check_dns_for_host("bad.com", ["1.2.3.4"], "A")
        )
        mock_logger.warning.assert_called_once_with(
            "Bad A record for bad.com: Expected {'1.2.3.4'}. Got: {'9.9.9.9'}"
        )


class TestCheckMxForHost(unittest.TestCase):
    """Test cases for check_mx_for_host."""

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    def test_success(self, mock_query_dns: mock.Mock):
        """Test success case with correct MX records."""
        mock_query_dns.return_value = MockAnswer([MockMxRdata(10, "mail.good.com.")])
        self.assertTrue(
            check_dns_for_hosting.check_mx_for_host("good.com", ["10 mail.good.com."])
        )
        mock_query_dns.assert_called_once_with("good.com", "MX")

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_failure_no_answer(self, mock_logger: mock.Mock, mock_query_dns: mock.Mock):
        """Test failure when there is no DNS answer for MX records."""
        mock_query_dns.return_value = None
        self.assertFalse(
            check_dns_for_hosting.check_mx_for_host("bad.com", ["10 mail.bad.com."])
        )
        mock_logger.warning.assert_called_once_with(
            "Error: Bad MX records for bad.com: Expected {'10 mail.bad.com.'}. "
            + "Got set()"
        )

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_failure_empty_rrset(
        self, mock_logger: mock.Mock, mock_query_dns: mock.Mock
    ):
        """Test failure when the MX answer has an empty rrset."""
        mock_query_dns.return_value = MockAnswer([])
        self.assertFalse(
            check_dns_for_hosting.check_mx_for_host("bad.com", ["10 mail.bad.com."])
        )
        mock_logger.warning.assert_called_once_with(
            "Error: Bad MX records for bad.com: Expected {'10 mail.bad.com.'}. "
            + "Got set()"
        )

    @mock.patch.object(check_dns_for_hosting, "query_dns")
    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_failure_wrong_records(
        self, mock_logger: mock.Mock, mock_query_dns: mock.Mock
    ):
        """Test failure when DNS returns incorrect MX records."""
        mock_query_dns.return_value = MockAnswer([MockMxRdata(99, "wrong.com.")])
        self.assertFalse(
            check_dns_for_hosting.check_mx_for_host("bad.com", ["10 mail.bad.com."])
        )
        mock_logger.warning.assert_called_once_with(
            "Error: Bad MX records for bad.com: Expected {'10 mail.bad.com.'}. "
            + "Got {'99 wrong.com.'}"
        )


class TestCheckSingleHost(unittest.TestCase):
    """Test cases for check_single_host."""

    @mock.patch.object(check_dns_for_hosting, "check_mx_for_host", return_value=True)
    @mock.patch.object(check_dns_for_hosting, "check_dns_for_host", return_value=True)
    def test_success_full_check(
        self, mock_check_dns: mock.Mock, mock_check_mx: mock.Mock
    ):
        """Test a successful check for a host with all options enabled."""
        config = check_dns_for_hosting.HostConfig(
            name="test.com",
            ipv4=["1.1.1.1"],
            ipv6=["::1"],
            mx=["10 mail.test.com."],
            check_www=True,
        )
        self.assertTrue(check_dns_for_hosting.check_single_host(config))
        mock_check_dns.assert_has_calls(
            [
                mock.call("test.com", ["1.1.1.1"], "A"),
                mock.call("test.com", ["::1"], "AAAA"),
                mock.call("www.test.com", ["1.1.1.1"], "A"),
                mock.call("www.test.com", ["::1"], "AAAA"),
            ]
        )
        mock_check_mx.assert_called_once_with("test.com", ["10 mail.test.com."])

    @mock.patch.object(check_dns_for_hosting, "check_dns_for_host", return_value=False)
    def test_failure_dns(self, _unused_mock_check_dns: mock.Mock):
        """Test failure when a primary DNS check fails."""
        config = check_dns_for_hosting.HostConfig(
            name="test.com", ipv4=["1.1.1.1"], ipv6=["::1"]
        )
        self.assertFalse(check_dns_for_hosting.check_single_host(config))


class TestMain(unittest.TestCase):
    """Test cases for the main function."""

    MOCK_CONFIG: list[check_dns_for_hosting.HostConfig] = [
        check_dns_for_hosting.HostConfig(
            name="test1.com", ipv4=["1.1.1.1"], ipv6=["::1"]
        ),
        check_dns_for_hosting.HostConfig(
            name="test2.com", ipv4=["2.2.2.2"], ipv6=["::2"]
        ),
    ]

    def test_main_success(self):
        """Test main returns 0 when all checks pass."""
        with (
            mock.patch.object(
                check_dns_for_hosting, "HOSTS_TO_CHECK", self.MOCK_CONFIG
            ),
            mock.patch.object(
                check_dns_for_hosting, "check_single_host", return_value=True
            ) as mock_check,
        ):
            self.assertEqual(check_dns_for_hosting.main(["script.py"]), 0)
            self.assertEqual(mock_check.call_count, 2)

    def test_main_failure(self):
        """Test main returns 1 when any check fails."""
        with (
            mock.patch.object(
                check_dns_for_hosting, "HOSTS_TO_CHECK", self.MOCK_CONFIG
            ),
            mock.patch.object(
                check_dns_for_hosting, "check_single_host", side_effect=[True, False]
            ) as mock_check,
        ):
            self.assertEqual(check_dns_for_hosting.main(["script.py"]), 1)
            self.assertEqual(mock_check.call_count, 2)

    @mock.patch.object(check_dns_for_hosting, "logger")
    def test_main_bad_args(self, mock_logger: mock.Mock):
        """Test main returns 1 when passed extra arguments."""
        self.assertEqual(check_dns_for_hosting.main(["script.py", "bad"]), 1)
        mock_logger.warning.assert_called()


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    unittest.main()
