"""Variant tool definitions for skilldiff examples."""

from __future__ import annotations

from http_utils import fetch_url_text


def _extract_title_from_html(html: str) -> str:
    lower = html.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No <title> tag found in HTML.")
    return html[start + 7 : end].strip()


def fetch_and_extract_title(url: str) -> str:
    """Fetch a URL and return the HTML page title."""
    html = fetch_url_text(url)
    return _extract_title_from_html(html)


def summarize_text(text: str, max_words: int = 20) -> str:
    """Return a short summary of the provided text."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + "..."
