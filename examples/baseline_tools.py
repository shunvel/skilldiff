"""Baseline tool definitions for skilldiff examples."""

from __future__ import annotations

from pathlib import Path

from http_utils import fetch_url_text


def fetch_url(url: str) -> str:
    """Fetch raw text content from a URL."""
    return fetch_url_text(url)


def read_text_file(path: str) -> str:
    """Read a local text file and return its contents."""
    return Path(path).read_text(encoding="utf-8")


def extract_title_from_html(html: str) -> str:
    """Extract a page title from raw HTML."""
    lower = html.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No <title> tag found in HTML.")
    return html[start + 7 : end].strip()
