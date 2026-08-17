"""Tests for reporter summary and CI exit decisions."""

import json
from pathlib import Path

from skilldiff.models import (
    AgentTrajectory,
    JudgeVerdict,
    RunReport,
    TaskDiffResult,
)
from skilldiff.reporter import (
    build_report,
    compute_summary,
    publish_report,
    save_report,
)


def _result(task_id: str, winner: str) -> TaskDiffResult:
    trajectory = AgentTrajectory(
        agent_id="baseline",
        steps=[],
        final_output="out",
        total_steps=1,
        execution_time_sec=1.0,
    )
    variant = trajectory.model_copy(update={"agent_id": "variant", "total_steps": 2})
    return TaskDiffResult(
        task_id=task_id,
        prompt="prompt",
        baseline_trajectory=trajectory,
        variant_trajectory=variant,
        verdict=JudgeVerdict(
            winner=winner,  # type: ignore[arg-type]
            baseline_score=6.0,
            variant_score=7.0 if winner == "variant" else 5.0,
            reasoning="test",
            tool_regression_detected=False,
        ),
        step_delta=1,
    )


def test_compute_summary_win_rate() -> None:
    results = [
        _result("a", "variant"),
        _result("b", "baseline"),
        _result("c", "tie"),
    ]
    summary = compute_summary(results)
    assert summary.total_tasks == 3
    assert summary.variant_wins == 1
    assert summary.variant_losses == 1
    assert summary.ties == 1
    assert summary.win_rate_pct == 33.33


def test_save_report_writes_json(tmp_path: Path) -> None:
    report = build_report([_result("a", "variant")], quick_mode=True)
    path = save_report(report, tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["variant_wins"] == 1
    assert payload["quick_mode"] is True


def test_publish_report_exit_on_loss(tmp_path: Path) -> None:
    report = RunReport(
        timestamp=build_report([]).timestamp,
        results=[_result("a", "baseline")],
        summary=compute_summary([_result("a", "baseline")]),
    )
    _, decision = publish_report(report, tmp_path, exit_on_loss=True)
    assert decision.code == 1
    assert decision.message is not None


def test_publish_report_min_win_rate(tmp_path: Path) -> None:
    report = build_report([_result("a", "variant")])
    _, decision = publish_report(report, tmp_path, min_win_rate=100.0)
    assert decision.code == 0

    report_loss = build_report([_result("a", "baseline")])
    _, decision_loss = publish_report(report_loss, tmp_path, min_win_rate=100.0)
    assert decision_loss.code == 1
