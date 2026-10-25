#!/usr/bin/env python3
"""Unit tests for check_urls."""

import gzip
import io
import json
import unittest
import zlib
from http import client as http_client
from typing import final
from unittest import mock

import check_urls


@final
class _StubHTTPResponse:
    """Typed HTTP response stub for testing HTTP connection handling."""

    def __init__(
        self,
        status: int = 200,
        reason: str = "OK",
        body: bytes = b"",
        location: str = "",
        content_encoding: str = "",
    ) -> None:
        """Initializes the stub response.

        Args:
            status: HTTP status code.
            reason: HTTP status reason phrase.
            body: Raw response payload bytes.
            location: Optional redirect Location header.
            content_encoding: Optional Content-Encoding header.
        """
        self.status: int = status
        self.reason: str = reason
        self._body: bytes = body
        self._headers: dict[str, str] = {
            "location": location,
            "content-encoding": content_encoding,
        }

    def read(self) -> bytes:
        """Returns the response body bytes.

        Returns:
            Raw response bytes.
        """
        return self._body

    def getheader(self, name: str, default: str = "") -> str:
        """Returns a response header value by name.

        Args:
            name: Header name.
            default: Default value if not found.

        Returns:
            Header string value.
        """
        return self._headers.get(name.lower(), default)


@final
class _StubHTTPConnection:
    """Typed HTTP connection stub for testing fetch_http_response."""

    def __init__(self, response: _StubHTTPResponse) -> None:
        """Initializes the stub connection.

        Args:
            response: Stub response to return from getresponse().
        """
        self._response: _StubHTTPResponse = response
        self.closed: bool = False

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Records an outgoing HTTP request.

        Args:
            method: HTTP method string.
            url: Request path and query string.
            headers: Optional request headers dictionary.
        """
        _ = (method, url, headers)

    def getresponse(self) -> _StubHTTPResponse:
        """Returns the configured stub HTTP response.

        Returns:
            The configured _StubHTTPResponse.
        """
        return self._response

    def close(self) -> None:
        """Marks the connection as closed."""
        self.closed = True


class TestCheckUrls(unittest.TestCase):
    """Tests for check_urls functions and CLI behavior."""

    def test_args_initialization_copies_urls(self) -> None:
        """Tests that Args copies the input list and defaults cleanly."""
        default_args = check_urls.Args()
        self.assertEqual(default_args.urls, [])
        self.assertEqual(default_args.timeout, check_urls.DEFAULT_TIMEOUT_SECONDS)

        source_urls = ["https://example.com/a"]
        custom_args = check_urls.Args(
            urls=source_urls,
            timeout=5.0,
            max_text_chars=200,
            pattern="shim",
        )
        source_urls.append("https://example.com/b")
        self.assertEqual(custom_args.urls, ["https://example.com/a"])
        self.assertEqual(custom_args.timeout, 5.0)
        self.assertEqual(custom_args.max_text_chars, 200)
        self.assertEqual(custom_args.pattern, "shim")

    def test_decode_response_bytes_encodings_and_fallbacks(self) -> None:
        """Tests gzip, deflate, invalid compression, and latin-1 decoding."""
        raw_utf8 = "Price: €12.69".encode()
        self.assertEqual(
            check_urls.decode_response_bytes(raw_utf8, ""),
            "Price: €12.69",
        )

        compressed_gzip = gzip.compress(raw_utf8)
        self.assertEqual(
            check_urls.decode_response_bytes(compressed_gzip, "gzip"),
            "Price: €12.69",
        )

        compressed_deflate = zlib.compress(raw_utf8)
        self.assertEqual(
            check_urls.decode_response_bytes(compressed_deflate, "deflate"),
            "Price: €12.69",
        )

        # Corrupted gzip payload falls back to raw bytes decoding
        self.assertEqual(
            check_urls.decode_response_bytes(raw_utf8, "gzip"),
            "Price: €12.69",
        )

        # Latin-1 £ symbol (0xa3) falls back cleanly when invalid UTF-8
        latin1_bytes = b"Cost: \xa319.99"
        self.assertEqual(
            check_urls.decode_response_bytes(latin1_bytes, ""),
            "Cost: £19.99",
        )

    def test_parse_html_content_extracts_jsonld_microdata_and_meta(
        self,
    ) -> None:
        """Tests extraction of title, JSON-LD, microdata, SKUs, and stock."""
        sample_html = """<!DOCTYPE html>
        <html>
        <head>
            <title>  Broadfix U-Shims  </title>
            <meta name="description" content="Recycled plastic horseshoe shims.">
            <meta name="unused" content="">
            <link rel="canonical" href="https://www.mydiy.ie/products/broadfix-u-shims.html">
            <meta property="product:price:amount" content="12.69">
            <meta property="product:price:currency" content="EUR">
            <meta name="sku" content="META-SKU-1">
            <meta property="product:availability" content="https://schema.org/InStock">
            <meta name="availability" content="DirectStock">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Broadfix U-Shims 60-Pack",
                "sku": "BFXUSTAC60",
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "EUR",
                    "price": "12.69",
                    "availability": "http://schema.org/InStock"
                }
            }
            </script>
            <script>const ignored = "€999.99";</script>
            <style>.hidden { content: "€888.88"; }</style>
        </head>
        <body>
            <h1>Broadfix U-Shims</h1>
            <span itemprop="price" content="12.69">€12.69</span>
            <span itemprop="priceCurrency" content="EUR"></span>
            <span itemprop="price">€15.00</span>
            <span itemprop="sku" content="ATTR-SKU"></span>
            <span itemprop="sku">INNER-SKU</span>
            <link itemprop="availability" href="https://schema.org/AvailableForDelivery">
            <input type="hidden" name="SKUID" value="154597">
            <div id="StockMsg">In Stock - Click &amp; Collect</div>
        </body>
        </html>
        """
        result = check_urls.parse_html_content(
            requested_url="https://short.example/u",
            final_url="https://www.mydiy.ie/products/broadfix-u-shims.html?id=1",
            status_code=200,
            html_text=sample_html,
            max_text_chars=300,
            pattern="broadfix|SKUID",
        )
        self.assertEqual(result.title, "Broadfix U-Shims")
        self.assertEqual(result.description, "Recycled plastic horseshoe shims.")
        self.assertEqual(
            result.canonical_url,
            "https://www.mydiy.ie/products/broadfix-u-shims.html",
        )
        self.assertFalse(result.bot_challenge_detected)
        self.assertIn("EUR 12.69", result.prices)
        self.assertIn("€12.69", result.prices)
        self.assertIn("€15.00", result.prices)
        self.assertNotIn("€999.99", result.prices)
        self.assertIn("META-SKU-1", result.skus)
        self.assertIn("BFXUSTAC60", result.skus)
        self.assertIn("ATTR-SKU", result.skus)
        self.assertIn("INNER-SKU", result.skus)
        self.assertIn("154597", result.skus)
        self.assertIn("InStock", result.availability)
        self.assertIn("AvailableForDelivery", result.availability)
        self.assertIn("In Stock", result.availability)
        self.assertTrue(len(result.pattern_matches) >= 2)
        self.assertIn("Broadfix U-Shims", result.text_excerpt)

    def test_parse_html_content_fallbacks_and_caps(self) -> None:
        """Tests og:title/og:url fallbacks, price/pattern caps, and bot challenge."""
        many_prices = " ".join(f"€{i}.99" for i in range(1, 20))
        many_lines = "\n".join(f"<p>match_item_{i}</p>" for i in range(15))
        sample_html = f"""
        <html>
        <head>
            <meta property="og:title" content="Human Verification">
            <meta property="og:url" content="https://example.com/canonical">
            <meta itemprop="price" content="42.00">
        </head>
        <body>
            <div>Verify you are human</div>
            <div>{many_prices}</div>
            {many_lines}
        </body>
        </html>
        """
        result = check_urls.parse_html_content(
            requested_url="https://example.com/item",
            final_url="https://example.com/item",
            status_code=403,
            html_text=sample_html,
            pattern="match_item_",
        )
        self.assertEqual(result.title, "Human Verification")
        self.assertEqual(result.canonical_url, "https://example.com/canonical")
        self.assertTrue(result.bot_challenge_detected)
        self.assertIn("42.00", result.prices)
        self.assertEqual(len(result.prices), 12)
        self.assertEqual(len(result.pattern_matches), 10)

    def test_create_connection_http_and_https(self) -> None:
        """Tests creating HTTPConnection and HTTPSConnection objects."""
        http_conn = check_urls.create_connection("http", "example.com", 80, 5.0)
        self.assertIsInstance(http_conn, http_client.HTTPConnection)
        http_conn.close()

        https_conn = check_urls.create_connection("https", "example.com", 443, 5.0)
        self.assertIsInstance(https_conn, http_client.HTTPSConnection)
        https_conn.close()

    def test_fetch_http_response_follows_redirect_and_handles_errors(
        self,
    ) -> None:
        """Tests redirect following, missing host, scheme error, and redirect cap."""
        with self.assertRaises(ValueError):
            _ = check_urls.fetch_http_response("ftp://example.com/file")

        with self.assertRaises(ValueError):
            _ = check_urls.fetch_http_response("https:///missing-host")

        conn1 = _StubHTTPConnection(
            _StubHTTPResponse(
                status=302,
                reason="Found",
                location="/p/ronseal/36047?sku=1",
            )
        )
        conn2 = _StubHTTPConnection(
            _StubHTTPResponse(
                status=200,
                reason="OK",
                body=b"<html><title>Ronseal</title></html>",
                content_encoding="",
            )
        )

        with mock.patch.object(
            check_urls,
            "create_connection",
            autospec=True,
            side_effect=[conn1, conn2],
        ):
            raw = check_urls.fetch_http_response("https://www.screwfix.ie/old")

        self.assertEqual(raw.final_url, "https://www.screwfix.ie/p/ronseal/36047?sku=1")
        self.assertEqual(raw.status_code, 200)
        self.assertTrue(conn1.closed)
        self.assertTrue(conn2.closed)

        loop_conn = _StubHTTPConnection(
            _StubHTTPResponse(
                status=301,
                reason="Moved",
                location="https://www.screwfix.ie/loop",
            )
        )
        with (
            mock.patch.object(
                check_urls,
                "create_connection",
                autospec=True,
                return_value=loop_conn,
            ),
            self.assertRaises(ValueError),
        ):
            _ = check_urls.fetch_http_response(
                "https://www.screwfix.ie/loop", max_redirects=1
            )

    def test_inspect_url_success_and_error_states(self) -> None:
        """Tests inspect_url for 200 OK, 403 error, and network exception."""
        ok_raw = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/p/ronseal/36047",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=(
                b"<html><head><title>Test Tool</title></head>"
                + b"<body><p>In Stock for \xe2\x82\xac52.95</p></body></html>"
            ),
        )
        forbidden_raw = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/p/blocked",
            status_code=403,
            reason="Forbidden",
            content_encoding="",
            body=b"<html><head><title>Human Verification</title></head></html>",
        )

        with mock.patch.object(
            check_urls,
            "fetch_http_response",
            autospec=True,
            side_effect=[ok_raw, forbidden_raw, OSError("DNS lookup failed")],
        ):
            res_ok = check_urls.inspect_url("https://short.url/ronseal")
            res_403 = check_urls.inspect_url("https://www.screwfix.ie/p/blocked")
            res_err = check_urls.inspect_url("https://nonexistent.invalid")

        self.assertEqual(res_ok.status_code, 200)
        self.assertIsNone(res_ok.error)
        self.assertIn("€52.95", res_ok.prices)

        self.assertEqual(res_403.status_code, 403)
        self.assertEqual(res_403.error, "HTTP 403: Forbidden")
        self.assertTrue(res_403.bot_challenge_detected)

        self.assertIsNone(res_err.status_code)
        self.assertIn("DNS lookup failed", res_err.error or "")

    def test_main_and_format_results_multiple_urls(self) -> None:
        """Tests CLI argument parsing, JSON output formatting, and exit code."""
        ok_result = check_urls.PageInspectionResult(
            requested_url="https://redirect.example/1",
            final_url="https://shop.example/product/1",
            status_code=200,
            error=None,
            bot_challenge_detected=False,
            title="Bosch GEX 40-150 Sander",
            description="Professional 150mm random orbit sander.",
            canonical_url="https://shop.example/canonical/1",
            prices=["EUR 329.00"],
            skus=["060137B200"],
            availability=["InStock"],
            pattern_matches=["Bosch GEX 40-150"],
            text_excerpt="Bosch GEX 40-150 Sander In Stock",
        )
        err_result = check_urls.PageInspectionResult(
            requested_url="https://shop.example/bad",
            final_url="https://shop.example/bad",
            status_code=403,
            error="HTTP 403: Forbidden",
            bot_challenge_detected=True,
            title="Just a moment...",
            description="",
            canonical_url="https://shop.example/bad",
            prices=[],
            skus=[],
            availability=[],
            pattern_matches=[],
            text_excerpt="",
        )

        out = io.StringIO()
        with mock.patch.object(
            check_urls,
            "inspect_url",
            autospec=True,
            side_effect=[ok_result, err_result],
        ):
            exit_code = check_urls.main(
                [
                    "--timeout",
                    "8",
                    "--max-text-chars",
                    "250",
                    "--pattern",
                    "Bosch",
                    "https://redirect.example/1",
                    "https://shop.example/bad",
                ],
                stdout=out,
            )

        self.assertEqual(exit_code, 1)
        output_text = out.getvalue()
        expected_json = (
            json.dumps(
                [ok_result.to_dict(), err_result.to_dict()],
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        self.assertEqual(output_text, expected_json)
        self.assertIn('"final_url": "https://shop.example/product/1"', output_text)
        self.assertIn('"prices": [\n      "EUR 329.00"\n    ]', output_text)
        self.assertIn('"bot_challenge_detected": true', output_text)


if __name__ == "__main__":
    _ = unittest.main()
