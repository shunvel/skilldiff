"""CLI integration tests."""

import json
from pathlib import Path

from typer.testing import CliRunner

from skilldiff.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_run_help_lists_provider_flags() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--provider" in result.output
    assert "--model" in result.output
    assert "--ollama-host" in result.output
    assert "--exit-on-loss" in result.output
    assert "--min-win-rate" in result.output
    assert "--swap-order" in result.output
