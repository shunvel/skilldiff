"""Provider-agnostic tool loading and JSON-schema declarations."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


_PYTHON_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type_for_annotation(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if isinstance(annotation, type) and annotation in _PYTHON_TYPE_TO_JSON:
        return _PYTHON_TYPE_TO_JSON[annotation]
    return "string"


def load_tools_from_script(script_path: Path) -> dict[str, Callable[..., Any]]:
    """Load public callables from a user-provided Python script."""
    if not script_path.exists():
        raise FileNotFoundError(f"Tool script not found: {script_path}")
    if script_path.suffix != ".py":
        raise ValueError(f"Tool script must be a .py file: {script_path}")

    module_name = f"skilldiff_tools_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tool script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    parent_dir = str(script_path.parent.resolve())
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    spec.loader.exec_module(module)

    tools: dict[str, Callable[..., Any]] = {}
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("_"):
            continue
        if obj.__module__ != module.__name__:
            continue
        tools[name] = obj
    return tools


def build_tool_specs(tools: dict[str, Callable[..., Any]]) -> list[ToolSpec]:
    """Build OpenAI-compatible tool specs from Python callables."""
    specs: list[ToolSpec] = []
    for name, func in tools.items():
        sig = inspect.signature(func)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            if param.kind not in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                continue
            properties[param_name] = {
                "type": _json_type_for_annotation(param.annotation),
                "description": f"Parameter `{param_name}` for `{name}`.",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required

        specs.append(
            ToolSpec(
                name=name,
                description=(func.__doc__ or f"Tool function `{name}`.").strip(),
                parameters=parameters,
            )
        )
    return specs


def tool_specs_to_openai_tools(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in specs
    ]
