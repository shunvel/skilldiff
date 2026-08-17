"""Rich console reporting and machine-readable JSON output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from skilldiff.models import RunReport, RunSummary, TaskDiffResult

console = Console()


@dataclass
class ExitDecision:
    code: int
    message: str | None = None


def _format_step_delta(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def compute_summary(results: list[TaskDiffResult]) -> RunSummary:
    total = len(results)
    wins = sum(1 for r in results if r.verdict.winner == "variant")
    losses = sum(1 for r in results if r.verdict.winner == "baseline")
    ties = sum(1 for r in results if r.verdict.winner == "tie")
    win_rate = (wins / total * 100.0) if total else 0.0
    return RunSummary(
        total_tasks=total,
        variant_wins=wins,
        variant_losses=losses,
        ties=ties,
        win_rate_pct=round(win_rate, 2),
    )


def render_results_table(results: list[TaskDiffResult]) -> Table:
    table = Table(title="skilldiff Results", show_header=True, header_style="bold cyan")
    table.add_column("Task ID", style="bold")
    table.add_column("Winner")
    table.add_column("Baseline Score", justify="right")
    table.add_column("Variant Score", justify="right")
    table.add_column("Step Delta", justify="right")
    table.add_column("Tool Regression?", justify="center")

    for result in results:
        winner_style = {
            "variant": "green",
            "baseline": "red",
            "tie": "yellow",
        }.get(result.verdict.winner, "white")
        table.add_row(
            result.task_id,
            f"[{winner_style}]{result.verdict.winner}[/{winner_style}]",
            f"{result.verdict.baseline_score:.1f}",
            f"{result.verdict.variant_score:.1f}",
            _format_step_delta(result.step_delta),
            "Yes" if result.verdict.tool_regression_detected else "No",
        )
    return table


def render_summary_panel(summary: RunSummary) -> Panel:
    body = (
        f"Total Tasks: {summary.total_tasks}\n"
        f"Variant Wins: {summary.variant_wins}\n"
        f"Variant Losses: {summary.variant_losses}\n"
        f"Ties: {summary.ties}\n"
        f"Win Rate: {summary.win_rate_pct:.1f}%"
    )
    return Panel(body, title="Summary", border_style="blue")


def save_report(report: RunReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"results_{timestamp}.json"
    payload = report.model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def publish_report(
    report: RunReport,
    output_dir: Path,
    *,
    exit_on_loss: bool = False,
    min_win_rate: float | None = None,
) -> tuple[Path, ExitDecision]:
    console.print(render_results_table(report.results))
    console.print(render_summary_panel(report.summary))
    output_path = save_report(report, output_dir)
    console.print(f"[dim]Saved results to {output_path}[/dim]")

    if exit_on_loss and report.summary.variant_losses > 0:
        return output_path, ExitDecision(
            code=1,
            message=f"Variant lost {report.summary.variant_losses} task(s).",
        )

    if min_win_rate is not None and report.summary.win_rate_pct < min_win_rate:
        return output_path, ExitDecision(
            code=1,
            message=(
                f"Win rate {report.summary.win_rate_pct:.1f}% is below "
                f"minimum {min_win_rate:.1f}%."
            ),
        )

    return output_path, ExitDecision(code=0)


def build_report(
    results: list[TaskDiffResult],
    *,
    quick_mode: bool = False,
    swap_order: bool = False,
) -> RunReport:
    return RunReport(
        timestamp=datetime.now(timezone.utc),
        results=results,
        summary=compute_summary(results),
        quick_mode=quick_mode,
        swap_order=swap_order,
    )
