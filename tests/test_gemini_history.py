"""Tests for Gemini thought_signature history preservation."""

import pytest
from google.genai import types

from skilldiff.llm import AgentTurn, ToolCall, _messages_to_gemini_contents, append_assistant_message


def _model_content(*, name: str, args: dict, signature: bytes) -> types.Content:
    try:
        part = types.Part(
            function_call=types.FunctionCall(name=name, args=args),
            thought_signature=signature,
        )
    except (TypeError, ValueError) as exc:
        pytest.skip(f"google-genai Part() rejected thought_signature: {exc}")
    return types.Content(role="model", parts=[part])


def test_append_assistant_message_preserves_gemini_model_content() -> None:
    model_content = _model_content(
        name="fetch_url",
        args={"url": "https://x.com"},
        signature=b"sig-bytes",
    )
    turn = AgentTurn(
        text="",
        tool_calls=[ToolCall(name="fetch_url", args={"url": "https://x.com"})],
        model_content=model_content,
    )
    messages: list[dict] = [{"role": "user", "content": "hello"}]
    append_assistant_message(messages, turn)

    assert len(messages) == 2
    assert messages[1]["gemini_content"] is model_content


def test_messages_to_gemini_contents_replays_raw_model_content() -> None:
    model_content = _model_content(
        name="read_text_file",
        args={"path": "a.txt"},
        signature=b"keep-me",
    )
    contents = _messages_to_gemini_contents(
        [
            {"role": "user", "content": "task"},
            {"role": "assistant", "gemini_content": model_content},
            {
                "role": "tool",
                "name": "read_text_file",
                "content": "file body",
            },
        ]
    )
    assert contents[1] is model_content
    assert contents[2].parts is not None
    assert contents[2].parts[0].function_response is not None
