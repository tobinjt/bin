import http.client
import io
import sys
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

import probe_arianetobin


class TestProbeWebsite(unittest.TestCase):
    @mock.patch.object(urllib.request, "urlopen")
    def test_probe_website_success(self, mock_urlopen):
        """Test that probe_website succeeds when the sentinel is found."""
        mock_response = mock.create_autospec(http.client.HTTPResponse, instance=True)
        mock_response.read.return_value = probe_arianetobin.SENTINEL.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        try:
            probe_arianetobin.probe_website(
                probe_arianetobin.WEBSITE, probe_arianetobin.SENTINEL
            )
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            probe_arianetobin.SentinelNotFoundError,
        ) as e:
            self.fail(f"probe_website raised an exception unexpectedly: {e}")

    @mock.patch.object(time, "sleep")
    @mock.patch.object(urllib.request, "urlopen")
    def test_probe_website_sentinel_not_found(self, mock_urlopen, mock_sleep):
        """Test that probe_website raises SentinelNotFoundError and retries."""
        mock_response = mock.create_autospec(http.client.HTTPResponse, instance=True)
        mock_response.read.return_value = b"some other content"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(probe_arianetobin.SentinelNotFoundError):
            probe_arianetobin.probe_website(
                probe_arianetobin.WEBSITE, probe_arianetobin.SENTINEL
            )

        self.assertEqual(mock_urlopen.call_count, probe_arianetobin.NUMBER_OF_ATTEMPTS)
        self.assertEqual(
            mock_sleep.call_count, probe_arianetobin.NUMBER_OF_ATTEMPTS - 1
        )

    @mock.patch.object(probe_arianetobin, "probe_website")
    def test_main_success(self, mock_probe_website):
        """Test that main returns 0 on success."""
        mock_probe_website.return_value = None
        self.assertEqual(probe_arianetobin.main(), 0)

    @mock.patch.object(probe_arianetobin, "probe_website")
    @mock.patch.object(sys, "stderr", new_callable=io.StringIO)
    def test_main_failure(self, mock_stderr, mock_probe_website):
        """Test that main returns 1 and prints to stderr on failure."""
        mock_probe_website.side_effect = probe_arianetobin.SentinelNotFoundError(
            "Test error"
        )
        self.assertEqual(probe_arianetobin.main(), 1)
        self.assertIn("Did not find sentinel", mock_stderr.getvalue())
        self.assertIn("Test error", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
