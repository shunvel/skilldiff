"""Tests for example HTTP helpers."""

from examples.http_utils import fetch_url_text


def test_fetch_url_text_reads_example_com() -> None:
    html = fetch_url_text("https://example.com")
    assert "<title>" in html.lower()
    assert "example domain" in html.lower()
