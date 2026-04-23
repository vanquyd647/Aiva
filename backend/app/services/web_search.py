"""Web search helpers used by search routes and chat citations."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests

_DDG_HTML_URL = "https://html.duckduckgo.com/html/"


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_result_url(raw_url: str) -> str:
    url = html.unescape(raw_url).strip()
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        params = parse_qs(parsed.query)
        uddg = params.get("uddg")
        if uddg and uddg[0].strip():
            return unquote(uddg[0].strip())

    return url


def _source_from_url(url: str) -> str:
    netloc = (urlparse(url).netloc or "").strip().lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _extract_snippet(block: str) -> str:
    snippet_patterns = [
        r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</a>',
        r'<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</div>',
    ]
    for pattern in snippet_patterns:
        match = re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL)
        if match:
            snippet = _strip_tags(match.group("snippet"))
            if snippet:
                return snippet[:900]
    return ""


def _parse_duckduckgo_html(content: str, limit: int) -> list[dict]:
    anchor_pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    matches = list(anchor_pattern.finditer(content))
    results: list[dict] = []
    if not matches:
        return results

    for index, match in enumerate(matches):
        resolved_url = _resolve_result_url(match.group("url"))
        if not resolved_url:
            continue

        title = _strip_tags(match.group("title"))
        if not title:
            continue

        next_pos = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        block = content[match.end() : next_pos]
        snippet = _extract_snippet(block)

        results.append(
            {
                "title": title[:400],
                "url": resolved_url[:1900],
                "snippet": snippet,
                "source": _source_from_url(resolved_url),
            }
        )
        if len(results) >= limit:
            break

    return results


def search_web(query: str, limit: int = 5, timeout_seconds: int = 12) -> list[dict]:
    """Run a web search via DuckDuckGo HTML endpoint and return normalized results."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    bounded_limit = max(1, min(limit, 10))
    try:
        response = requests.get(
            _DDG_HTML_URL,
            params={"q": clean_query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except Exception:
        return []

    return _parse_duckduckgo_html(response.text, bounded_limit)
