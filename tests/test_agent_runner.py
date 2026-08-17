"""Tests for dynamic tool loading."""

from pathlib import Path

import pytest

from skilldiff.tools_schema import build_tool_specs, load_tools_from_script

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_baseline_tools_from_examples() -> None:
    tools = load_tools_from_script(REPO_ROOT / "examples/baseline_tools.py")
    assert "fetch_url" in tools
    assert "read_text_file" in tools
    assert "_fetch_url" not in tools


def test_load_variant_tools_from_examples() -> None:
    tools = load_tools_from_script(REPO_ROOT / "examples/variant_tools.py")
    assert "fetch_and_extract_title" in tools
    assert "summarize_text" in tools


def test_build_function_declarations_has_parameters() -> None:
    tools = load_tools_from_script(REPO_ROOT / "examples/baseline_tools.py")
    declarations = build_tool_specs(tools)
    names = {decl.name for decl in declarations}
    assert "fetch_url" in names
    fetch_decl = next(d for d in declarations if d.name == "fetch_url")
    assert "url" in fetch_decl.parameters.get("properties", {})


def test_load_tools_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_tools_from_script(Path("does_not_exist.py"))


def test_load_tools_non_py_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "tools.txt"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a .py file"):
        load_tools_from_script(bad)
