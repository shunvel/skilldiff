"""LLM backends for agent execution and judging."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal
from urllib import error, request

from google import genai
from google.genai import types
from pydantic import ValidationError

from skilldiff.models import JudgeVerdict
from skilldiff.tools_schema import ToolSpec, tool_specs_to_openai_tools

ProviderName = Literal["gemini", "ollama"]

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

JUDGE_SYSTEM = (
    "You are an impartial evaluator comparing two AI agent trajectories. "
    "Score each agent from 0.0 to 10.0 based on task success, efficiency, "
    "tool usage quality, and alignment with the expected outcome. "
    "Detect tool regressions when the variant misuses tools, fails where "
    "baseline succeeded, or introduces unnecessary complexity."
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class AgentTurn:
    text: str
    tool_calls: list[ToolCall]
    model_content: Any | None = None


class LLMBackend(ABC):
    model: str

    @abstractmethod
    async def agent_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        temperature: float,
    ) -> AgentTurn:
        raise NotImplementedError

    @abstractmethod
    async def judge_verdict(self, *, system: str, prompt: str) -> JudgeVerdict:
        raise NotImplementedError


def create_backend(
    provider: ProviderName,
    *,
    model: str | None = None,
    api_key: str | None = None,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
) -> LLMBackend:
    if provider == "gemini":
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when --provider=gemini")
        return GeminiBackend(api_key=api_key, model=model or DEFAULT_GEMINI_MODEL)
    return OllamaBackend(host=ollama_host, model=model or DEFAULT_OLLAMA_MODEL)


class GeminiBackend(LLMBackend):
    def __init__(self, *, api_key: str, model: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def agent_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        temperature: float,
    ) -> AgentTurn:
        contents = _messages_to_gemini_contents(messages)
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "system_instruction": system,
        }
        if tools:
            declarations = [
                types.FunctionDeclaration(
                    name=spec.name,
                    description=spec.description,
                    parameters=types.Schema(
                        type="OBJECT",  # type: ignore[arg-type]
                        properties={
                            key: types.Schema(
                                type=value.get("type", "string").upper(),
                                description=value.get("description"),
                            )
                            for key, value in spec.parameters.get("properties", {}).items()
                        }
                        or None,
                        required=spec.parameters.get("required"),
                    ),
                )
                for spec in tools
            ]
            config_kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,  # type: ignore[arg-type]
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return _gemini_response_to_turn(response)

    async def judge_verdict(self, *, system: str, prompt: str) -> JudgeVerdict:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=JudgeVerdict,
            ),
        )
        raw = response.text or "{}"
        return _parse_judge_verdict(raw)


class OllamaBackend(LLMBackend):
    def __init__(self, *, host: str, model: str) -> None:
        self.host = host.rstrip("/")
        self.model = model

    async def agent_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        temperature: float,
    ) -> AgentTurn:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tool_specs_to_openai_tools(tools)

        data = await _post_json(f"{self.host}/api/chat", payload)
        message = data.get("message") or {}
        tool_calls = _parse_ollama_tool_calls(message.get("tool_calls") or [])
        return AgentTurn(text=(message.get("content") or "").strip(), tool_calls=tool_calls)

    async def judge_verdict(self, *, system: str, prompt: str) -> JudgeVerdict:
        schema = JudgeVerdict.model_json_schema()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (f"{prompt}\n\nRespond with JSON matching this schema:\n{json.dumps(schema, indent=2)}"),
                },
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        data = await _post_json(f"{self.host}/api/chat", payload)
        raw = (data.get("message") or {}).get("content") or "{}"
        return _parse_judge_verdict(raw)


async def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    import asyncio

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def _send() -> dict[str, Any]:
        try:
            with request.urlopen(req, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not reach Ollama at {url}. Is `ollama serve` running?") from exc

    return await asyncio.to_thread(_send)


def _parse_judge_verdict(raw: str) -> JudgeVerdict:
    try:
        return JudgeVerdict.model_validate_json(raw)
    except ValidationError as exc:
        return JudgeVerdict(
            winner="tie",
            baseline_score=0.0,
            variant_score=0.0,
            reasoning=f"Judge response failed validation: {exc}. Raw: {raw[:500]}",
            tool_regression_detected=False,
            fix_suggestion="Inspect judge prompt/response schema configuration.",
        )


def _parse_ollama_tool_calls(raw_calls: list[Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for item in raw_calls:
        function = item.get("function") if isinstance(item, dict) else None
        if not function:
            continue
        name = function.get("name") or "unknown_tool"
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        calls.append(ToolCall(name=name, args=dict(arguments)))
    return calls


def _messages_to_gemini_contents(messages: list[dict[str, Any]]) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in messages:
        gemini_content = message.get("gemini_content")
        if gemini_content is not None:
            contents.append(gemini_content)
            continue

        role = message["role"]
        if role == "assistant":
            parts: list[types.Part] = []
            if message.get("content"):
                parts.append(types.Part.from_text(text=message["content"]))
            for call in message.get("tool_calls") or []:
                parts.append(
                    types.Part.from_function_call(
                        name=call["name"],
                        args=call.get("args") or {},
                    )
                )
            if parts:
                contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=message["name"],
                            response={"result": message.get("content", "")},
                        )
                    ],
                )
            )
        else:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=message.get("content") or "")],
                )
            )
    return contents


def _gemini_response_to_turn(response: types.GenerateContentResponse) -> AgentTurn:
    text = (response.text or "").strip()
    candidate = response.candidates[0] if response.candidates else None
    parts = candidate.content.parts if candidate and candidate.content else []

    if not text and parts:
        texts = [part.text for part in parts if getattr(part, "text", None)]
        text = "\n".join(t for t in texts if t).strip()

    tool_calls: list[ToolCall] = []
    for part in parts or []:
        function_call = getattr(part, "function_call", None)
        if function_call is None:
            continue
        tool_calls.append(
            ToolCall(
                name=function_call.name or "unknown_tool",
                args=dict(function_call.args or {}),
            )
        )

    model_content = candidate.content if candidate and candidate.content else None
    return AgentTurn(text=text, tool_calls=tool_calls, model_content=model_content)


def append_assistant_message(
    messages: list[dict[str, Any]],
    turn: AgentTurn,
) -> None:
    if turn.model_content is not None:
        messages.append({"role": "assistant", "gemini_content": turn.model_content})
        return

    message: dict[str, Any] = {"role": "assistant", "content": turn.text}
    if turn.tool_calls:
        message["tool_calls"] = [{"name": call.name, "args": call.args} for call in turn.tool_calls]
    messages.append(message)


def append_tool_result(
    messages: list[dict[str, Any]],
    *,
    name: str,
    content: str,
) -> None:
    messages.append({"role": "tool", "name": name, "content": content})
