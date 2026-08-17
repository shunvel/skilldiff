"""Tests for the demo-repo fixture suite."""

import json
from pathlib import Path

from skilldiff.models import Task
from skilldiff.tools_schema import load_tools_from_script

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "fixtures/demo-repo"


def test_fixture_tasks_cover_sanity_and_eval() -> None:
    raw = json.loads((FIXTURE / "tasks.json").read_text(encoding="utf-8"))
    tasks = [Task.model_validate(item) for item in raw]
    ids = {task.id for task in tasks}
    assert ids == {
        "fetch_page_title",
        "summarize_notes",
        "parse_title_offline",
        "summarize_given_text",
    }
    sanity = [task for task in tasks if "sanity" in task.tags]
    eval_tasks = [task for task in tasks if "eval" in task.tags]
    assert len(sanity) == 2
    assert len(eval_tasks) == 2


def test_fixture_tools_load() -> None:
    baseline = load_tools_from_script(FIXTURE / "baseline_tools.py")
    variant = load_tools_from_script(FIXTURE / "variant_tools.py")
    assert "extract_title_from_html" in baseline
    assert "fetch_and_extract_title" in variant
    assert "summarize_text" in variant
