import io
import sys
import time
import unittest
from unittest import mock

import requests

import probe_arianetobin


class TestProbeWebsite(unittest.TestCase):
    @mock.patch.object(requests, "get")
    def test_probe_website_success(self, mock_get: mock.Mock):
        """Test that probe_website succeeds when the sentinel is found."""
        mock_response = requests.Response()
        mock_response._content = probe_arianetobin.SENTINEL.encode()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        try:
            probe_arianetobin.probe_website(
                probe_arianetobin.WEBSITE, probe_arianetobin.SENTINEL
            )
        except (
            requests.exceptions.RequestException,
            probe_arianetobin.SentinelNotFoundError,
        ) as e:
            self.fail(f"probe_website raised an exception unexpectedly: {e}")

    @mock.patch.object(time, "sleep", return_value=None)
    @mock.patch.object(requests, "get")
    def test_probe_website_sentinel_not_found(
        self, mock_get: mock.Mock, mock_sleep: mock.Mock
    ):
        """Test that probe_website raises SentinelNotFoundError and retries."""
        mock_response = requests.Response()
        mock_response._content = "some other content".encode()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with self.assertRaises(probe_arianetobin.SentinelNotFoundError):
            probe_arianetobin.probe_website(
                probe_arianetobin.WEBSITE, probe_arianetobin.SENTINEL
            )

        self.assertEqual(mock_get.call_count, probe_arianetobin.NUMBER_OF_ATTEMPTS)
        self.assertEqual(
            mock_sleep.call_count, probe_arianetobin.NUMBER_OF_ATTEMPTS - 1
        )

    @mock.patch.object(probe_arianetobin, "probe_website")
    def test_main_success(self, mock_probe_website: mock.Mock):
        """Test that main returns 0 on success."""
        mock_probe_website.return_value = None
        self.assertEqual(probe_arianetobin.main(), 0)

    @mock.patch.object(probe_arianetobin, "probe_website")
    @mock.patch.object(sys, "stderr", new_callable=io.StringIO)
    def test_main_failure(
        self, mock_stderr: io.StringIO, mock_probe_website: mock.Mock
    ):
        """Test that main returns 1 and prints to stderr on failure."""
        mock_probe_website.side_effect = probe_arianetobin.SentinelNotFoundError(
            "Test error"
        )
        self.assertEqual(probe_arianetobin.main(), 1)
        self.assertIn("Did not find sentinel", mock_stderr.getvalue())
        self.assertIn("Test error", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
