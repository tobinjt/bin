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

        with (
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                side_effect=[ok_raw, forbidden_raw, OSError("DNS lookup failed")],
            ),
            mock.patch.object(
                check_urls,
                "fetch_nextjs_data_response",
                autospec=True,
                return_value=None,
            ),
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

    def test_parse_nextjs_json_content(self) -> None:
        """Tests parsing Next.js JSON product data and edge cases."""
        sample_json = json.dumps(
            {
                "pageProps": {
                    "models": {
                        "enrichedData": {
                            "productDetails": {
                                "skuId": "885KJ",
                                "longDescription": "Broadfix Plastic U-Shims Assorted 60 Pcs",
                                "overview": "Easily stacked to achieve any shimming height.",
                                "bullets": ["Resealable Packaging", "Colour-Coded"],
                                "technicalSpecifications": [
                                    {"name": "Brand", "value": "Broadfix"},
                                    {"name": "Pack Size", "value": "60"},
                                ],
                                "priceInformation": {
                                    "currentPriceIncVat": {
                                        "currency": "EUR",
                                        "amount": 11.85,
                                    },
                                    "currentPriceExVat": {
                                        "currency": "EUR",
                                        "amount": 9.63,
                                    },
                                },
                                "fulfilmentAvailability": {
                                    "canBeDelivered": True,
                                    "canBeCollected": True,
                                },
                                "productAvailabilityStatus": "AVAILABLE",
                            },
                            "seoOverrides": {
                                "title": "Broadfix Plastic U-Shims - Screwfix",
                                "canonicalUrl": "/p/broadfix-plastic-u-shims-assorted-60-pcs/885kj",
                            },
                        }
                    }
                }
            }
        )
        res = check_urls.parse_nextjs_json_content(
            requested_url="https://short.url/shims",
            final_url="https://www.screwfix.ie/p/broadfix-plastic-u-shims-assorted-60-pcs/885kj",
            json_text=sample_json,
            pattern="Resealable",
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.error)
        self.assertFalse(res.bot_challenge_detected)
        self.assertEqual(res.title, "Broadfix Plastic U-Shims - Screwfix")
        self.assertEqual(
            res.description, "Easily stacked to achieve any shimming height."
        )
        self.assertEqual(
            res.canonical_url,
            "https://www.screwfix.ie/p/broadfix-plastic-u-shims-assorted-60-pcs/885kj",
        )
        self.assertIn("EUR 11.85", res.prices)
        self.assertIn("EUR 9.63 (ex VAT)", res.prices)
        self.assertIn("885KJ", res.skus)
        self.assertIn("available for delivery", res.availability)
        self.assertIn("click & collect", res.availability)
        self.assertIn("AVAILABLE", res.availability)
        self.assertIn("Brand: Broadfix", res.text_excerpt)
        self.assertTrue(len(res.pattern_matches) > 0)

        # Invalid JSON or non-dict payloads return None
        self.assertIsNone(
            check_urls.parse_nextjs_json_content(
                "https://example.com", "https://example.com", "not json"
            )
        )
        self.assertIsNone(
            check_urls.parse_nextjs_json_content(
                "https://example.com", "https://example.com", "[]"
            )
        )

    def test_parse_nextjs_json_content_out_of_stock(self) -> None:
        """Tests Next.js parsing when an item is out of stock."""
        sample_json = json.dumps(
            {
                "pageProps": {
                    "productDetails": {
                        "skuId": "999XX",
                        "longDescription": "Discontinued Item",
                        "fulfilmentAvailability": {
                            "canBeDelivered": False,
                            "canBeCollected": False,
                        },
                    }
                }
            }
        )
        res = check_urls.parse_nextjs_json_content(
            requested_url="https://example.com/item",
            final_url="https://example.com/item",
            json_text=sample_json,
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertIn("out of stock", res.availability)

    def test_find_nested_dict_in_list_and_primitives(self) -> None:
        """Tests find_nested_dict when traversing lists and missing keys."""
        data = [{"a": 1}, {"target": {"found": "yes"}}]
        found = check_urls.find_nested_dict(data, "target")
        self.assertEqual(found, {"found": "yes"})
        self.assertIsNone(check_urls.find_nested_dict("not a container", "target"))
        self.assertIsNone(check_urls.find_nested_dict([1, 2, 3], "target"))

    def test_parse_nextjs_json_content_edge_cases(self) -> None:
        """Tests branch coverage for Next.js JSON edge cases and fallbacks."""
        items: list[dict[str, object]] = [
            {"pattern_line": f"match_pattern_{i}"} for i in range(15)
        ]
        sparse_dict: dict[str, object] = {
            "items": [
                {
                    "productDetails": {
                        "productName": "Minimal Product",
                        "bullets": [" ", 123],
                        "technicalSpecifications": [
                            "invalid_spec",
                            {"name": "OnlyName"},
                            {"value": "OnlyVal"},
                        ],
                        "priceInformation": {
                            "currentPriceIncVat": {
                                "currency": "EUR",
                                "amount": "invalid",
                            },
                            "currentPriceExVat": {
                                "currency": "EUR",
                                "amount": "invalid",
                            },
                        },
                        "skuId": None,
                    },
                    "seoOverrides": {
                        "canonicalUrl": None,
                        "productDescription": "Minimal Description",
                    },
                }
            ],
            "extra_matches": items,
        }
        sparse_json = json.dumps(sparse_dict, indent=2)
        res = check_urls.parse_nextjs_json_content(
            requested_url="https://example.com/p/item",
            final_url="https://example.com/p/item",
            json_text=sparse_json,
            pattern="match_pattern_",
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.title, "Minimal Product")
        self.assertEqual(res.description, "Minimal Description")
        self.assertEqual(res.canonical_url, "https://example.com/p/item")
        self.assertEqual(res.prices, [])
        self.assertEqual(res.skus, [])
        self.assertEqual(len(res.pattern_matches), 10)

        # Test empty title and description path
        empty_json = json.dumps({"pageProps": {}})
        empty_res = check_urls.parse_nextjs_json_content(
            requested_url="https://example.com/empty",
            final_url="https://example.com/empty",
            json_text=empty_json,
        )
        self.assertIsNotNone(empty_res)
        assert empty_res is not None
        self.assertEqual(empty_res.title, "")
        self.assertEqual(empty_res.text_excerpt, "")

    def test_inspect_url_202_fallback_failure(self) -> None:
        """Tests inspect_url handling HTTP 202 when Next.js data route is missing."""
        resp_202 = check_urls.RawHTTPResponse(
            final_url="https://example.com/accepted",
            status_code=202,
            reason="Accepted",
            content_encoding="",
            body=b"<html><head><title></title></head><body></body></html>",
        )
        with (
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                return_value=resp_202,
            ),
            mock.patch.object(
                check_urls,
                "fetch_nextjs_data_response",
                autospec=True,
                return_value=None,
            ),
        ):
            res = check_urls.inspect_url("https://example.com/accepted")

        self.assertEqual(res.status_code, 202)
        self.assertEqual(res.error, "HTTP 202: Accepted")
        self.assertTrue(res.bot_challenge_detected)

    def test_get_nextjs_build_id_and_caching(self) -> None:
        """Tests extracting Next.js build ID from homepage HTML and caching."""
        check_urls.clear_build_id_cache()
        ok_home = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=b'<html><body><script id="__NEXT_DATA__">{"buildId":"test-build-123"}</script></body></html>',
        )
        with mock.patch.object(
            check_urls,
            "fetch_http_response",
            autospec=True,
            return_value=ok_home,
        ):
            build_id = check_urls.get_nextjs_build_id("www.screwfix.ie")
            self.assertEqual(build_id, "test-build-123")
            # Second call uses cache and does not fetch
            cached = check_urls.get_nextjs_build_id("www.screwfix.ie")
            self.assertEqual(cached, "test-build-123")

        bad_home = check_urls.RawHTTPResponse(
            final_url="https://other.example/",
            status_code=404,
            reason="Not Found",
            content_encoding="",
            body=b"",
        )
        with mock.patch.object(
            check_urls,
            "fetch_http_response",
            autospec=True,
            return_value=bad_home,
        ):
            self.assertIsNone(check_urls.get_nextjs_build_id("other.example"))

        no_build = check_urls.RawHTTPResponse(
            final_url="https://nobuild.example/",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=b"<html>No build id</html>",
        )
        with mock.patch.object(
            check_urls,
            "fetch_http_response",
            autospec=True,
            return_value=no_build,
        ):
            self.assertIsNone(check_urls.get_nextjs_build_id("nobuild.example"))

        with mock.patch.object(
            check_urls,
            "fetch_http_response",
            autospec=True,
            side_effect=OSError("network down"),
        ):
            self.assertIsNone(check_urls.get_nextjs_build_id("down.example"))

    def test_fetch_nextjs_data_response(self) -> None:
        """Tests fetching Next.js data route and error paths."""
        self.assertIsNone(check_urls.fetch_nextjs_data_response("https://example.com/"))
        self.assertIsNone(check_urls.fetch_nextjs_data_response("https:///p/1"))

        with mock.patch.object(
            check_urls,
            "get_nextjs_build_id",
            autospec=True,
            return_value=None,
        ):
            self.assertIsNone(
                check_urls.fetch_nextjs_data_response("https://example.com/p/1")
            )

        data_resp = check_urls.RawHTTPResponse(
            final_url="https://example.com/_next/data/b1/p/1.json?q=test",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=b'{"pageProps":{}}',
        )
        with (
            mock.patch.object(
                check_urls,
                "get_nextjs_build_id",
                autospec=True,
                return_value="b1",
            ),
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                return_value=data_resp,
            ),
        ):
            res = check_urls.fetch_nextjs_data_response(
                "https://example.com/p/1?q=test"
            )
            self.assertIsNotNone(res)
            assert res is not None
            self.assertEqual(res.status_code, 200)

        with (
            mock.patch.object(
                check_urls,
                "get_nextjs_build_id",
                autospec=True,
                return_value="b1",
            ),
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                side_effect=OSError("fail"),
            ),
        ):
            self.assertIsNone(
                check_urls.fetch_nextjs_data_response("https://example.com/p/1")
            )

        error_resp = check_urls.RawHTTPResponse(
            final_url="https://example.com/_next/data/b1/p/1.json",
            status_code=500,
            reason="Server Error",
            content_encoding="",
            body=b"error",
        )
        with (
            mock.patch.object(
                check_urls,
                "get_nextjs_build_id",
                autospec=True,
                return_value="b1",
            ),
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                return_value=error_resp,
            ),
        ):
            self.assertIsNone(
                check_urls.fetch_nextjs_data_response("https://example.com/p/1")
            )

    def test_inspect_url_nextjs_fallback_success(self) -> None:
        """Tests that a bot-challenged URL falls back to Next.js data route."""
        challenge_raw = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/p/sample/123",
            status_code=405,
            reason="Not Allowed",
            content_encoding="",
            body=b"<html><head><title>Human Verification</title></head></html>",
        )
        sample_json = json.dumps(
            {
                "pageProps": {
                    "productDetails": {
                        "skuId": "123",
                        "longDescription": "Fallback Product",
                        "priceInformation": {
                            "currentPriceIncVat": {
                                "currency": "EUR",
                                "amount": 19.99,
                            }
                        },
                        "fulfilmentAvailability": {"canBeDelivered": True},
                    }
                }
            }
        )
        data_raw = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/_next/data/b1/p/sample/123.json",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=sample_json.encode(),
        )

        with (
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                return_value=challenge_raw,
            ),
            mock.patch.object(
                check_urls,
                "fetch_nextjs_data_response",
                autospec=True,
                return_value=data_raw,
            ),
        ):
            res = check_urls.inspect_url("https://www.screwfix.ie/p/sample/123")

        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.error)
        self.assertFalse(res.bot_challenge_detected)
        self.assertEqual(res.title, "Fallback Product")
        self.assertIn("EUR 19.99", res.prices)
        self.assertIn("123", res.skus)

        # Fallback payload is invalid JSON, so it returns original error
        bad_json_raw = check_urls.RawHTTPResponse(
            final_url="https://www.screwfix.ie/_next/data/b1/p/sample/123.json",
            status_code=200,
            reason="OK",
            content_encoding="",
            body=b"not valid json",
        )
        with (
            mock.patch.object(
                check_urls,
                "fetch_http_response",
                autospec=True,
                return_value=challenge_raw,
            ),
            mock.patch.object(
                check_urls,
                "fetch_nextjs_data_response",
                autospec=True,
                return_value=bad_json_raw,
            ),
        ):
            res_bad = check_urls.inspect_url("https://www.screwfix.ie/p/sample/123")
        self.assertEqual(res_bad.status_code, 405)
        self.assertEqual(res_bad.error, "HTTP 405: Not Allowed")


if __name__ == "__main__":
    _ = unittest.main()
