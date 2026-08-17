"""skilldiff CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated, Optional, cast

import typer
from dotenv import load_dotenv
from rich.console import Console

from skilldiff.agent_runner import SimpleAgentRunner
from skilldiff.judge import TrajectoryJudge
from skilldiff.llm import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    ProviderName,
    create_backend,
)
from skilldiff.models import (
    AgentTrajectory,
    JudgeVerdict,
    Task,
    TaskDiffResult,
    TrajectoryStep,
)
from skilldiff.reporter import build_report, publish_report

app = typer.Typer(
    name="skilldiff",
    help="A/B test AI agent skills, prompts, and tool definitions with LLM-as-a-Judge.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _load_tasks(tasks_path: Path, quick: bool) -> list[Task]:
    if not tasks_path.exists():
        raise typer.BadParameter(f"Tasks file not found: {tasks_path}")

    raw = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks = [Task.model_validate(item) for item in raw]
    if quick:
        tasks = [task for task in tasks if "sanity" in task.tags]
    if not tasks:
        raise typer.BadParameter("No tasks to run after filtering.")
    return tasks


def _resolve_backend(
    provider: ProviderName,
    model: str | None,
    ollama_host: str,
):
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") if provider == "gemini" else None
    if provider == "gemini" and not api_key:
        raise typer.BadParameter(
            "GEMINI_API_KEY is required when --provider=gemini. "
            "Copy .env.example to .env and set your key, or use --provider=ollama."
        )
    try:
        return create_backend(
            provider,
            model=model,
            api_key=api_key,
            ollama_host=ollama_host,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _mock_demo_results() -> list[TaskDiffResult]:
    baseline_fetch = AgentTrajectory(
        agent_id="baseline",
        steps=[
            TrajectoryStep(
                step_number=1,
                thought="I need the page title.",
                tool_name="fetch_url",
                tool_args={"url": "https://example.com"},
                observation="Example Domain",
            ),
            TrajectoryStep(
                step_number=2,
                thought="The title is Example Domain.",
                observation=None,
            ),
        ],
        final_output="Example Domain",
        total_steps=2,
        execution_time_sec=1.2,
    )
    variant_fetch = AgentTrajectory(
        agent_id="variant",
        steps=[
            TrajectoryStep(
                step_number=1,
                thought="I'll fetch and extract the title in one step.",
                tool_name="fetch_and_extract_title",
                tool_args={"url": "https://example.com"},
                observation="Example Domain",
            ),
            TrajectoryStep(
                step_number=2,
                thought="Done in one tool call.",
                observation=None,
            ),
        ],
        final_output="Example Domain",
        total_steps=2,
        execution_time_sec=0.8,
    )

    baseline_summarize = AgentTrajectory(
        agent_id="baseline",
        steps=[
            TrajectoryStep(
                step_number=1,
                thought="Read the file contents.",
                tool_name="read_text_file",
                tool_args={"path": "notes.txt"},
                observation="skilldiff helps compare agent tool sets quickly.",
            ),
            TrajectoryStep(
                step_number=2,
                thought="Summarize manually.",
                observation=None,
            ),
        ],
        final_output="A tool for comparing agent configurations.",
        total_steps=2,
        execution_time_sec=1.5,
    )
    variant_summarize = AgentTrajectory(
        agent_id="variant",
        steps=[
            TrajectoryStep(
                step_number=1,
                thought="Use the summarize tool.",
                tool_name="summarize_text",
                tool_args={"text": "skilldiff helps compare agent tool sets quickly."},
                observation="Compares agent tool sets quickly.",
            ),
        ],
        final_output="Compares agent tool sets quickly.",
        total_steps=1,
        execution_time_sec=0.6,
    )

    return [
        TaskDiffResult(
            task_id="fetch_page_title",
            prompt="Fetch the title of https://example.com",
            baseline_trajectory=baseline_fetch,
            variant_trajectory=variant_fetch,
            verdict=JudgeVerdict(
                winner="variant",
                baseline_score=7.5,
                variant_score=8.8,
                reasoning="Variant achieved the same result with a specialized tool.",
                tool_regression_detected=False,
                fix_suggestion=None,
            ),
            step_delta=0,
        ),
        TaskDiffResult(
            task_id="summarize_notes",
            prompt="Summarize the contents of notes.txt in one sentence.",
            baseline_trajectory=baseline_summarize,
            variant_trajectory=variant_summarize,
            verdict=JudgeVerdict(
                winner="variant",
                baseline_score=6.0,
                variant_score=9.0,
                reasoning="Variant completed the task in fewer steps with a dedicated summarize tool.",
                tool_regression_detected=False,
                fix_suggestion=None,
            ),
            step_delta=-1,
        ),
    ]


async def _run_suite(
    tasks: list[Task],
    runner: SimpleAgentRunner,
    judge: TrajectoryJudge,
    *,
    swap_order: bool,
) -> list[TaskDiffResult]:
    results: list[TaskDiffResult] = []
    for task in tasks:
        baseline, variant = await runner.run_pair(task)
        verdict = await judge.evaluate(
            task,
            baseline,
            variant,
            swap_order=swap_order,
        )
        results.append(
            TaskDiffResult(
                task_id=task.id,
                prompt=task.prompt,
                baseline_trajectory=baseline,
                variant_trajectory=variant,
                verdict=verdict,
                step_delta=variant.total_steps - baseline.total_steps,
            )
        )
    return results


@app.command()
def run(
    tasks: Annotated[
        Path,
        typer.Option("--tasks", help="Path to tasks JSON file."),
    ] = Path("tasks.json"),
    quick: Annotated[
        bool,
        typer.Option("--quick", help="Run only tasks tagged with 'sanity'."),
    ] = False,
    baseline_tools: Annotated[
        Path,
        typer.Option("--baseline-tools", help="Python script with baseline tool functions."),
    ] = cast(Path, ...),
    variant_tools: Annotated[
        Path,
        typer.Option("--variant-tools", help="Python script with variant tool functions."),
    ] = cast(Path, ...),
    provider: Annotated[
        ProviderName,
        typer.Option(
            "--provider",
            help="LLM provider: gemini (cloud) or ollama (local).",
        ),
    ] = "gemini",
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help=f"Model name (default: {DEFAULT_GEMINI_MODEL} or {DEFAULT_OLLAMA_MODEL}).",
        ),
    ] = None,
    ollama_host: Annotated[
        str,
        typer.Option(
            "--ollama-host",
            help="Ollama server URL when --provider=ollama.",
        ),
    ] = DEFAULT_OLLAMA_HOST,
    exit_on_loss: Annotated[
        bool,
        typer.Option("--exit-on-loss", help="Exit with code 1 if variant loses any task."),
    ] = False,
    min_win_rate: Annotated[
        Optional[float],
        typer.Option("--min-win-rate", help="Exit with code 1 if win rate is below this value."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for machine-readable JSON results."),
    ] = Path(".agent_diff"),
    swap_order: Annotated[
        bool,
        typer.Option(
            "--swap-order",
            help="Run a swapped-order judge pass to reduce position bias.",
        ),
    ] = False,
) -> None:
    """Run baseline vs variant agents across a task suite."""
    backend = _resolve_backend(provider, model, ollama_host)
    task_list = _load_tasks(tasks, quick)

    console.print(f"[dim]Provider: {provider} | Model: {backend.model}[/dim]")

    runner = SimpleAgentRunner(
        backend=backend,
        baseline_tools_path=baseline_tools,
        variant_tools_path=variant_tools,
        quick=quick,
    )
    judge = TrajectoryJudge(backend=backend)

    results = asyncio.run(_run_suite(task_list, runner, judge, swap_order=swap_order))
    report = build_report(results, quick_mode=quick, swap_order=swap_order)
    _, decision = publish_report(
        report,
        output_dir,
        exit_on_loss=exit_on_loss,
        min_win_rate=min_win_rate,
    )
    if decision.message:
        console.print(f"[red]{decision.message}[/red]")
    raise typer.Exit(decision.code)


@app.command()
def demo(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for machine-readable JSON results."),
    ] = Path(".agent_diff"),
) -> None:
    """Run a zero-config visual demo using mock agents (no API key required)."""
    results = _mock_demo_results()
    report = build_report(results, quick_mode=True, swap_order=False)
    publish_report(report, output_dir)
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
