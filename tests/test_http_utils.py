"""Tests for example HTTP helpers."""

from unittest.mock import MagicMock, patch

from examples.http_utils import fetch_url_text


def test_fetch_url_text_uses_certifi_context() -> None:
    html = b"<html><head><title>Example Domain</title></head></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = html
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False

    with (
        patch("examples.http_utils.urlopen", return_value=mock_response) as mocked_open,
        patch("examples.http_utils.ssl.create_default_context") as mocked_ssl,
    ):
        result = fetch_url_text("https://example.com")

    assert "Example Domain" in result
    mocked_open.assert_called_once()
    mocked_ssl.assert_called_once()
