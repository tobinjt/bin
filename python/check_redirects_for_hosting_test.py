import unittest
from unittest import mock

import requests

import check_redirects_for_hosting


class CheckRedirectsForHostingTest(unittest.TestCase):
    @mock.patch.object(requests, "head")
    def test_check_single_redirect_success(self, mock_head):
        mock_response = mock.create_autospec(requests.Response, instance=True)
        mock_response.url = "https://www.arianetobin.ie/"
        mock_head.return_value = mock_response

        check_redirects_for_hosting.check_single_redirect(
            "https://www.arianetobin.ie/", "http://ariane.ie/"
        )

    @mock.patch.object(requests, "head")
    def test_check_single_redirect_failure(self, mock_head):
        mock_response = mock.create_autospec(requests.Response, instance=True)
        mock_response.url = "http://some-other-url.com"
        mock_head.return_value = mock_response

        with self.assertRaises(check_redirects_for_hosting.MissingRedirectError):
            check_redirects_for_hosting.check_single_redirect(
                "https://www.arianetobin.ie/", "http://ariane.ie/"
            )

    @mock.patch.object(check_redirects_for_hosting, "check_single_redirect")
    def test_check_redirects_success(self, mock_check_single_redirect):
        errors = check_redirects_for_hosting.check_redirects(
            "https://www.arianetobin.ie/", "http://ariane.ie/", "https://ariane.ie/"
        )
        self.assertEqual(errors, [])
        self.assertEqual(mock_check_single_redirect.call_count, 2)

    @mock.patch.object(check_redirects_for_hosting, "check_single_redirect")
    def test_check_redirects_failure(self, mock_check_single_redirect):
        mock_check_single_redirect.side_effect = (
            check_redirects_for_hosting.MissingRedirectError("test error")
        )
        errors = check_redirects_for_hosting.check_redirects(
            "https://www.arianetobin.ie/", "http://ariane.ie/"
        )
        self.assertEqual(errors, ["test error"])

    @mock.patch.object(check_redirects_for_hosting, "check_redirects")
    def test_main_success(self, mock_check_redirects):
        mock_check_redirects.return_value = []
        self.assertEqual(check_redirects_for_hosting.main(), 0)

    @mock.patch.object(check_redirects_for_hosting, "check_redirects")
    def test_main_failure(self, mock_check_redirects):
        mock_check_redirects.return_value = ["error1", "error2"]
        self.assertEqual(check_redirects_for_hosting.main(), 1)


if __name__ == "__main__":
    unittest.main()
