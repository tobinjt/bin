#!/usr/bin/env python3
"""Fetches one or more URLs and extracts product, price, stock, and page metadata.

Follows HTTP redirects (including search engine grounding redirects), extracts
HTML metadata, schema.org/JSON-LD product data (price, currency, SKU, stock
availability), currency mentions, optional regex matches, and a clean text
excerpt for fast URL and product verification.

Usage examples:
    ./check_urls.py https://www.screwfix.ie/p/broadfix-plastic-u-shims-assorted-60-pcs/885kj
    ./check_urls.py --pattern "broadfix|shim" https://www.mydiy.ie/products/broadfix-u-shims.html
"""

import argparse
import dataclasses
import gzip
import html
import io
import json
import re
import ssl
import sys
import zlib
from collections import abc as collections_abc
from html import parser as html_parser
from http import client as http_client
from typing import Any, TypedDict, final, override
from urllib import parse as urllib_parse

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_TEXT_CHARS = 800
MAX_REDIRECTS = 10
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    + "AppleWebKit/537.36 (KHTML, like Gecko) "
    + "Chrome/131.0.0.0 Safari/537.36"
)

_IGNORED_TEXT_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "template", "head"}
)

_PRICE_TEXT_RE = re.compile(
    r"(?:[€£$]\s?\d{1,5}(?:,\d{3})*(?:\.\d{2})?|\b(?:EUR|GBP|USD)\s?\d{1,5}(?:,\d{3})*(?:\.\d{2})?)"
)
_JSONLD_PRICE_RE = re.compile(
    r'"(?:price|lowPrice|highPrice)"\s*:\s*"?(\d+(?:\.\d{1,2})?)"?',
    re.IGNORECASE,
)
_JSONLD_CURRENCY_RE = re.compile(
    r'"priceCurrency"\s*:\s*"([A-Z]{3})"',
    re.IGNORECASE,
)
_JSONLD_SKU_RE = re.compile(
    r'"(?:sku|productID|mpn)"\s*:\s*"([^"\r\n]{1,64})"',
    re.IGNORECASE,
)
_JSONLD_AVAILABILITY_RE = re.compile(
    r'"availability"\s*:\s*"(?:https?://schema\.org/)?([A-Za-z]+)"',
    re.IGNORECASE,
)
_STOCK_TEXT_RE = re.compile(
    r"\b(in stock|out of stock|available for delivery|click & collect|"
    + r"discontinued|currently unavailable|sold out|low stock)\b",
    re.IGNORECASE,
)
_BOT_CHALLENGE_RE = re.compile(
    r"(human verification|verify you are human|cf-browser-verification|"
    + r"challenge-platform|access denied|just a moment\.\.\.|captcha)",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


@final
class Args(argparse.Namespace):
    """Typed command-line arguments for check_urls."""

    @override
    def __init__(
        self,
        urls: list[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
        pattern: str = "",
        **kwargs: Any,  # pyright: ignore [reportAny,reportExplicitAny]
    ) -> None:
        """Initializes typed command-line arguments.

        Args:
            urls: List of URLs to fetch and inspect.
            timeout: Socket timeout in seconds per URL request.
            max_text_chars: Maximum number of visible text characters to include.
            pattern: Optional case-insensitive regex pattern to search for.
        """
        super().__init__(**kwargs)
        self.urls: list[str] = list(urls) if urls is not None else []
        self.timeout: float = timeout
        self.max_text_chars: int = max_text_chars
        self.pattern: str = pattern


class PageInspectionDict(TypedDict):
    """JSON-serializable dictionary schema for PageInspectionResult."""

    requested_url: str
    final_url: str
    status_code: int | None
    error: str | None
    bot_challenge_detected: bool
    title: str
    description: str
    canonical_url: str
    prices: list[str]
    skus: list[str]
    availability: list[str]
    pattern_matches: list[str]
    text_excerpt: str


@dataclasses.dataclass(frozen=True)
class PageInspectionResult:
    """Structured result of fetching and inspecting a single URL."""

    requested_url: str
    final_url: str
    status_code: int | None
    error: str | None
    bot_challenge_detected: bool
    title: str
    description: str
    canonical_url: str
    prices: list[str]
    skus: list[str]
    availability: list[str]
    pattern_matches: list[str]
    text_excerpt: str

    def to_dict(self) -> PageInspectionDict:
        """Converts this result into a JSON-serializable PageInspectionDict.

        Returns:
            A PageInspectionDict matching this instance's fields.
        """
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "error": self.error,
            "bot_challenge_detected": self.bot_challenge_detected,
            "title": self.title,
            "description": self.description,
            "canonical_url": self.canonical_url,
            "prices": list(self.prices),
            "skus": list(self.skus),
            "availability": list(self.availability),
            "pattern_matches": list(self.pattern_matches),
            "text_excerpt": self.text_excerpt,
        }


@dataclasses.dataclass(frozen=True)
class RawHTTPResponse:
    """Typed HTTP response data returned by fetch_http_response."""

    final_url: str
    status_code: int
    reason: str
    content_encoding: str
    body: bytes


@final
class _MetadataHTMLParser(html_parser.HTMLParser):
    """HTML parser that extracts metadata, microdata, JSON-LD, and visible text."""

    def __init__(self) -> None:
        """Initializes the parser state."""
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.meta_title: str = ""
        self.description: str = ""
        self.canonical_url: str = ""
        self.prices: list[str] = []
        self.currencies: list[str] = []
        self.skus: list[str] = []
        self.availability: list[str] = []
        self.jsonld_blocks: list[str] = []
        self.visible_text_chunks: list[str] = []

        self._in_title: bool = False
        self._in_jsonld: bool = False
        self._current_jsonld_parts: list[str] = []
        self._ignored_depth: int = 0
        self._active_itemprop: str = ""

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Processes an opening HTML tag and its attributes.

        Args:
            tag: Lowercase HTML tag name.
            attrs: List of (attribute_name, attribute_value) pairs.
        """
        attr_map: dict[str, str] = {
            key.lower(): (val or "").strip() for key, val in attrs
        }

        if tag == "title":
            self._in_title = True
        elif tag == "script":
            script_type = attr_map.get("type", "").lower()
            if "ld+json" in script_type:
                self._in_jsonld = True
                self._current_jsonld_parts = []
            self._ignored_depth += 1
        elif tag in _IGNORED_TEXT_TAGS:
            self._ignored_depth += 1
        elif tag == "link":
            rel = attr_map.get("rel", "").lower()
            href = attr_map.get("href", "")
            if "canonical" in rel and href and not self.canonical_url:
                self.canonical_url = href
        elif tag == "meta":
            self._handle_meta_tag(attr_map)

        self._handle_microdata_attrs(attr_map)

    def _handle_meta_tag(self, attr_map: dict[str, str]) -> None:
        """Extracts metadata from a <meta> tag's attributes.

        Args:
            attr_map: Lowercase attribute dictionary for the meta tag.
        """
        name = (
            attr_map.get("name")
            or attr_map.get("property")
            or attr_map.get("itemprop")
            or ""
        ).lower()
        content = attr_map.get("content", "")
        if not name or not content:
            return

        if name in {"og:title", "twitter:title"} and not self.meta_title:
            self.meta_title = content
        elif (
            name in {"description", "og:description", "twitter:description"}
            and not self.description
        ):
            self.description = content
        elif name == "og:url" and not self.canonical_url:
            self.canonical_url = content
        elif name in {
            "product:price:amount",
            "og:price:amount",
            "price",
        }:
            _append_unique(self.prices, content)
        elif name in {
            "product:price:currency",
            "og:price:currency",
            "pricecurrency",
        }:
            _append_unique(self.currencies, content)
        elif name in {"sku", "productid", "mpn"}:
            _append_unique(self.skus, content)
        elif name in {"availability", "product:availability"}:
            _append_unique(self.availability, _clean_schema_uri(content))

    def _handle_microdata_attrs(self, attr_map: dict[str, str]) -> None:
        """Extracts schema.org microdata and input SKUs from element attributes.

        Args:
            attr_map: Lowercase attribute dictionary for the element.
        """
        itemprop = attr_map.get("itemprop", "").lower()
        content = attr_map.get("content") or attr_map.get("href") or ""
        if itemprop == "price":
            if content:
                _append_unique(self.prices, content)
            else:
                self._active_itemprop = "price"
        elif itemprop == "pricecurrency" and content:
            _append_unique(self.currencies, content)
        elif itemprop in {"sku", "productid", "mpn"}:
            if content:
                _append_unique(self.skus, content)
            else:
                self._active_itemprop = "sku"
        elif itemprop == "availability" and content:
            _append_unique(self.availability, _clean_schema_uri(content))

        input_name = attr_map.get("name", "").upper()
        input_val = attr_map.get("value", "")
        if input_name in {"SKU", "SKUID", "PRODUCT_ID"} and input_val:
            _append_unique(self.skus, input_val)

    @override
    def handle_endtag(self, tag: str) -> None:
        """Processes a closing HTML tag.

        Args:
            tag: Lowercase HTML tag name.
        """
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._in_jsonld:
                self.jsonld_blocks.append("".join(self._current_jsonld_parts))
                self._in_jsonld = False
                self._current_jsonld_parts = []
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif tag in _IGNORED_TEXT_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)

        self._active_itemprop = ""

    @override
    def handle_data(self, data: str) -> None:
        """Processes character data inside HTML elements.

        Args:
            data: Decoded character text inside the current element.
        """
        if self._in_title:
            self.title_parts.append(data)
        if self._in_jsonld:
            self._current_jsonld_parts.append(data)

        if self._active_itemprop == "price":
            _append_unique(self.prices, data)
        elif self._active_itemprop == "sku":
            _append_unique(self.skus, data)

        if self._ignored_depth == 0 and not self._in_title:
            stripped = data.strip()
            if stripped:
                self.visible_text_chunks.append(stripped)


def _append_unique(items: list[str], value: str) -> None:
    """Appends a non-empty string to a list if not already present.

    Args:
        items: Target list of strings.
        value: Candidate string to append.
    """
    normalized = _WHITESPACE_RE.sub(" ", html.unescape(value)).strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _clean_schema_uri(value: str) -> str:
    """Strips leading schema.org URL prefixes from availability strings.

    Args:
        value: Raw schema availability value or URI.

    Returns:
        The human-readable availability token.
    """
    for prefix in ("https://schema.org/", "http://schema.org/"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def decode_response_bytes(raw_bytes: bytes, content_encoding: str) -> str:
    """Decompresses and decodes HTTP response bytes into a UTF-8 string.

    Args:
        raw_bytes: Raw bytes read from the HTTP response body.
        content_encoding: Value of the Content-Encoding HTTP header.

    Returns:
        Decoded text content of the response body.
    """
    encoding = content_encoding.lower().strip()
    decompressed = raw_bytes
    try:
        if encoding == "gzip":
            decompressed = gzip.decompress(raw_bytes)
        elif encoding == "deflate":
            decompressed = zlib.decompress(raw_bytes)
    except (OSError, zlib.error):
        decompressed = raw_bytes

    try:
        return decompressed.decode("utf-8")
    except UnicodeDecodeError:
        return decompressed.decode("latin-1", errors="replace")


def parse_html_content(
    requested_url: str,
    final_url: str,
    status_code: int | None,
    html_text: str,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    pattern: str = "",
) -> PageInspectionResult:
    """Parses HTML text into a structured PageInspectionResult.

    Args:
        requested_url: Original URL requested by the caller.
        final_url: Effective URL after following HTTP redirects.
        status_code: HTTP status code returned by the server.
        html_text: Decoded HTML document text.
        max_text_chars: Maximum characters of visible text excerpt to retain.
        pattern: Optional case-insensitive regex pattern to match against text.

    Returns:
        A populated PageInspectionResult instance.
    """
    parser = _MetadataHTMLParser()
    parser.feed(html_text)
    parser.close()

    raw_title = "".join(parser.title_parts).strip() or parser.meta_title
    title = _WHITESPACE_RE.sub(" ", raw_title).strip()
    description = _WHITESPACE_RE.sub(" ", parser.description).strip()
    canonical_url = parser.canonical_url or final_url

    prices = list(parser.prices)
    currencies = list(parser.currencies)
    skus = list(parser.skus)
    availability = list(parser.availability)

    for block in parser.jsonld_blocks:
        for match in _JSONLD_CURRENCY_RE.finditer(block):
            _append_unique(currencies, match.group(1).upper())
        for match in _JSONLD_PRICE_RE.finditer(block):
            _append_unique(prices, match.group(1))
        for match in _JSONLD_SKU_RE.finditer(block):
            _append_unique(skus, match.group(1))
        for match in _JSONLD_AVAILABILITY_RE.finditer(block):
            _append_unique(availability, match.group(1))

    currency_prefix = f"{currencies[0]} " if currencies else ""
    formatted_prices: list[str] = []
    for price in prices:
        if price and price[0].isdigit() and currency_prefix:
            _append_unique(formatted_prices, f"{currency_prefix}{price}")
        else:
            _append_unique(formatted_prices, price)

    visible_text = _WHITESPACE_RE.sub(" ", " ".join(parser.visible_text_chunks)).strip()

    for match in _PRICE_TEXT_RE.finditer(visible_text):
        _append_unique(formatted_prices, match.group(0))
        if len(formatted_prices) >= 12:
            break

    for match in _STOCK_TEXT_RE.finditer(visible_text):
        _append_unique(availability, match.group(1))

    bot_challenge = bool(
        _BOT_CHALLENGE_RE.search(title)
        or (
            len(visible_text) < 600
            and _BOT_CHALLENGE_RE.search(visible_text) is not None
        )
    )

    pattern_matches: list[str] = []
    if pattern:
        compiled = re.compile(pattern, re.IGNORECASE)
        for line in html_text.splitlines():
            cleaned_line = _WHITESPACE_RE.sub(" ", line).strip()
            if compiled.search(cleaned_line):
                _append_unique(pattern_matches, cleaned_line[:240])
                if len(pattern_matches) >= 10:
                    break

    excerpt = visible_text[:max_text_chars]
    return PageInspectionResult(
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        error=None,
        bot_challenge_detected=bot_challenge,
        title=title,
        description=description,
        canonical_url=canonical_url,
        prices=formatted_prices,
        skus=skus,
        availability=availability,
        pattern_matches=pattern_matches,
        text_excerpt=excerpt,
    )


def create_connection(
    scheme: str,
    host: str,
    port: int | None,
    timeout: float,
) -> http_client.HTTPConnection:
    """Creates an HTTPConnection or HTTPSConnection for the given scheme and host.

    Args:
        scheme: URL scheme ('http' or 'https').
        host: Target hostname.
        port: Optional target TCP port.
        timeout: Socket timeout in seconds.

    Returns:
        An HTTPConnection or HTTPSConnection instance.
    """
    if scheme == "https":
        context = ssl.create_default_context()
        return http_client.HTTPSConnection(
            host, port=port, timeout=timeout, context=context
        )
    return http_client.HTTPConnection(host, port=port, timeout=timeout)


def fetch_http_response(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = MAX_REDIRECTS,
) -> RawHTTPResponse:
    """Fetches an HTTP/HTTPS URL following redirects using strictly typed http.client.

    Args:
        url: Target HTTP or HTTPS URL.
        timeout: Socket timeout in seconds per request.
        max_redirects: Maximum number of 3xx redirects to follow.

    Returns:
        A RawHTTPResponse containing the final URL, status, headers, and body.

    Raises:
        ValueError: If the URL scheme is unsupported, host is missing, or
            too many redirects occur.
        OSError: If a network or socket error occurs.
        http_client.HTTPException: If an HTTP protocol error occurs.
    """
    current_url = url
    for _ in range(max_redirects + 1):
        parsed = urllib_parse.urlsplit(current_url)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")
        host = parsed.hostname
        if not host:
            raise ValueError(f"Missing hostname in URL: {current_url!r}")

        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        conn = create_connection(scheme, host, parsed.port, timeout)
        try:
            conn.request(
                "GET",
                path,
                headers={
                    "Host": parsed.netloc,
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        + "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-IE,en-GB;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "close",
                },
            )
            response = conn.getresponse()
            status_code = response.status
            reason = response.reason
            location = response.getheader("Location", "")
            content_encoding = response.getheader("Content-Encoding", "")
            body = response.read()
        finally:
            conn.close()

        if status_code in {301, 302, 303, 307, 308} and location:
            current_url = urllib_parse.urljoin(current_url, location)
            continue

        return RawHTTPResponse(
            final_url=current_url,
            status_code=status_code,
            reason=reason,
            content_encoding=content_encoding,
            body=body,
        )

    raise ValueError(f"Too many redirects (exceeded {max_redirects})")


def inspect_url(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    pattern: str = "",
) -> PageInspectionResult:
    """Fetches a single URL over HTTP/HTTPS and returns its inspection result.

    Args:
        url: Target URL to fetch (must use http:// or https://).
        timeout: Timeout in seconds for the network request.
        max_text_chars: Maximum characters of visible page text to include.
        pattern: Optional case-insensitive regex pattern to search for.

    Returns:
        A PageInspectionResult containing status, redirect target, and metadata.
    """
    try:
        raw_response = fetch_http_response(url, timeout=timeout)
    except (ValueError, OSError, http_client.HTTPException) as exc:
        return PageInspectionResult(
            requested_url=url,
            final_url=url,
            status_code=None,
            error=str(exc),
            bot_challenge_detected=False,
            title="",
            description="",
            canonical_url="",
            prices=[],
            skus=[],
            availability=[],
            pattern_matches=[],
            text_excerpt="",
        )

    html_text = decode_response_bytes(raw_response.body, raw_response.content_encoding)
    result = parse_html_content(
        requested_url=url,
        final_url=raw_response.final_url,
        status_code=raw_response.status_code,
        html_text=html_text,
        max_text_chars=max_text_chars,
        pattern=pattern,
    )
    if raw_response.status_code >= 400:
        return dataclasses.replace(
            result,
            error=f"HTTP {raw_response.status_code}: {raw_response.reason}",
        )
    return result


def format_results(
    results: collections_abc.Sequence[PageInspectionResult],
) -> str:
    """Serializes a sequence of PageInspectionResult objects to a JSON string.

    Args:
        results: The inspection results to serialize.

    Returns:
        Pretty-printed JSON array string.
    """
    payload: list[PageInspectionDict] = [result.to_dict() for result in results]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def parse_args(argv: collections_abc.Sequence[str] | None = None) -> Args:
    """Parses command-line arguments into a typed Args namespace.

    Args:
        argv: Optional list of argument strings; defaults to sys.argv[1:].

    Returns:
        Populated Args namespace instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Fetch one or more URLs, follow redirects, and output product "
            + "metadata (title, price, SKU, availability, and text excerpt) as JSON."
        )
    )
    _ = parser.add_argument(
        "urls",
        nargs="+",
        help="One or more HTTP/HTTPS URLs to fetch and inspect.",
    )
    _ = parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Timeout in seconds per URL request "
            + f"(default: {DEFAULT_TIMEOUT_SECONDS})."
        ),
    )
    _ = parser.add_argument(
        "-m",
        "--max-text-chars",
        type=int,
        default=DEFAULT_MAX_TEXT_CHARS,
        help=(
            "Maximum visible text characters in text_excerpt "
            + f"(default: {DEFAULT_MAX_TEXT_CHARS})."
        ),
    )
    _ = parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default="",
        help="Optional case-insensitive regex pattern to match lines.",
    )
    return parser.parse_args(argv, namespace=Args())


def main(
    argv: collections_abc.Sequence[str] | None = None,
    stdout: io.TextIOBase | None = None,
) -> int:
    """Entry point for the check_urls CLI tool.

    Args:
        argv: Command-line arguments (excluding program name).
        stdout: Output stream; defaults to sys.stdout when None.

    Returns:
        Exit code (0 if all URLs succeeded, 1 if any URL returned an error).
    """
    args = parse_args(argv)
    out = stdout if stdout is not None else sys.stdout
    exit_code = 0
    results: list[PageInspectionResult] = []

    for url in args.urls:
        result = inspect_url(
            url=url,
            timeout=args.timeout,
            max_text_chars=args.max_text_chars,
            pattern=args.pattern,
        )
        results.append(result)
        if result.error is not None:
            exit_code = 1

    _ = out.write(format_results(results) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
