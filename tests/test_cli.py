"""CLI integration tests."""

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from skilldiff.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(result) -> str:
    raw = "".join(
        part for part in (result.output, getattr(result, "stdout", ""), getattr(result, "stderr", "") or "") if part
    )
    return _ANSI.sub("", raw)


def test_demo_exits_zero_and_writes_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["demo", "--output-dir", ".agent_diff"])
    combined = f"{result.output}\n{result.stdout}\n{getattr(result, 'stderr', '')}"
    assert result.exit_code == 0, combined
    assert "skilldiff Results" in combined
    assert "Win Rate" in combined

    output_dir = tmp_path / ".agent_diff"
    files = list(output_dir.glob("results_*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["summary"]["total_tasks"] == 2
    assert len(payload["results"]) == 2


def test_run_requires_api_key_for_gemini(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("skilldiff.main.load_dotenv", lambda *args, **kwargs: None)
    baseline = REPO_ROOT / "examples/baseline_tools.py"
    variant = REPO_ROOT / "examples/variant_tools.py"
    tasks = REPO_ROOT / "tasks.json"
    result = runner.invoke(
        app,
        [
            "run",
            "--tasks",
            str(tasks),
            "--baseline-tools",
            str(baseline),
            "--variant-tools",
            str(variant),
            "--provider",
            "gemini",
        ],
    )
    assert result.exit_code != 0
    assert "GEMINI_API_KEY" in result.output


def test_run_help_lists_provider_flags(monkeypatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    result = runner.invoke(app, ["run", "--help"], env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0, result.output
    text = re.sub(r"\s+", "", _plain(result))
    for flag in ("--provider", "--model", "--ollama-host", "--exit-on-loss", "--min-win-rate", "--swap-order"):
        assert flag in text, _plain(result)
