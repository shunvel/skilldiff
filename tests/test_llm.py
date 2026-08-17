"""Tests for Ollama backend helpers."""

from skilldiff.llm import _parse_ollama_tool_calls, create_backend
from skilldiff.models import JudgeVerdict


def test_parse_ollama_tool_calls_from_dict_args() -> None:
    calls = _parse_ollama_tool_calls(
        [
            {
                "function": {
                    "name": "read_text_file",
                    "arguments": {"path": "notes.txt"},
                }
            }
        ]
    )
    assert len(calls) == 1
    assert calls[0].name == "read_text_file"
    assert calls[0].args == {"path": "notes.txt"}


def test_parse_ollama_tool_calls_from_json_string_args() -> None:
    calls = _parse_ollama_tool_calls(
        [
            {
                "function": {
                    "name": "summarize_text",
                    "arguments": '{"text": "hello world"}',
                }
            }
        ]
    )
    assert calls[0].args == {"text": "hello world"}


def test_create_ollama_backend_without_api_key() -> None:
    backend = create_backend("ollama", model="qwen3:8b")
    assert backend.model == "qwen3:8b"


def test_create_gemini_backend_requires_api_key() -> None:
    try:
        create_backend("gemini")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_judge_verdict_schema_has_required_fields() -> None:
    schema = JudgeVerdict.model_json_schema()
    assert "winner" in schema["properties"]
