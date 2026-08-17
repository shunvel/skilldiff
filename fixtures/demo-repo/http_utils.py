"""Shared HTTP helpers for skilldiff examples."""

from __future__ import annotations

import ssl
from urllib.request import Request, urlopen

import certifi


def fetch_url_text(url: str, *, timeout: int = 10) -> str:
    """Fetch raw text from a URL using certifi CA bundle (macOS-safe)."""
    req = Request(url, headers={"User-Agent": "skilldiff/0.1.0"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(req, timeout=timeout, context=context) as response:
        return response.read().decode("utf-8", errors="replace")
