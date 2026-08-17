"""Tests for example HTTP helpers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from skilldiff.tools_schema import load_tools_from_script

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fetch_url_text_uses_certifi_context() -> None:
    tools = load_tools_from_script(REPO_ROOT / "examples/http_utils.py")
    fetch_url_text = tools["fetch_url_text"]
    module = sys.modules[fetch_url_text.__module__]

    html = b"<html><head><title>Example Domain</title></head></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = html
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False

    with patch.object(module, "urlopen", return_value=mock_response) as mocked_open:
        with patch.object(module.ssl, "create_default_context") as mocked_ssl:
            result = fetch_url_text("https://example.com")

    assert "Example Domain" in result
    mocked_open.assert_called_once()
    mocked_ssl.assert_called_once()
