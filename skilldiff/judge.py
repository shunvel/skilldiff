"""LLM-as-a-Judge engine."""

from __future__ import annotations

import json
from typing import Optional

from skilldiff.llm import JUDGE_SYSTEM, LLMBackend
from skilldiff.models import AgentTrajectory, JudgeVerdict, Task


def _format_trajectory(label: str, trajectory: AgentTrajectory) -> str:
    lines = [
        f"=== {label.upper()} ({trajectory.agent_id}) ===",
        f"Total steps: {trajectory.total_steps}",
        f"Execution time (sec): {trajectory.execution_time_sec}",
        f"Error: {trajectory.error or 'none'}",
        f"Final output: {trajectory.final_output}",
        "Steps:",
    ]
    for step in trajectory.steps:
        lines.append(f"  Step {step.step_number}:")
        lines.append(f"    Thought: {step.thought}")
        if step.tool_name:
            lines.append(f"    Tool: {step.tool_name}({json.dumps(step.tool_args or {})})")
        if step.observation is not None:
            lines.append(f"    Observation: {step.observation}")
    return "\n".join(lines)


def short_circuit_verdict(
    baseline: AgentTrajectory,
    variant: AgentTrajectory,
) -> Optional[JudgeVerdict]:
    """Return a tie verdict without calling the LLM when outputs are identical."""
    if baseline.final_output == variant.final_output and baseline.total_steps == variant.total_steps:
        return JudgeVerdict(
            winner="tie",
            baseline_score=5.0,
            variant_score=5.0,
            reasoning=("Short-circuit: final outputs match exactly and step counts are equal."),
            tool_regression_detected=False,
            fix_suggestion=None,
        )
    return None


def enforce_score_parity(verdict: JudgeVerdict) -> JudgeVerdict:
    """Ensure variant winner has strictly higher score than baseline."""
    if verdict.winner == "variant" and verdict.variant_score <= verdict.baseline_score:
        return verdict.model_copy(
            update={
                "winner": "tie",
                "reasoning": (
                    f"{verdict.reasoning}\n\n"
                    "Score parity guard: winner was variant but variant_score "
                    f"({verdict.variant_score}) did not exceed baseline_score "
                    f"({verdict.baseline_score}); coerced to tie."
                ),
            }
        )
    return verdict


class TrajectoryJudge:
    """Compare baseline vs variant trajectories using a configured LLM backend."""

    def __init__(self, backend: LLMBackend) -> None:
        self.backend = backend

    async def evaluate(
        self,
        task: Task,
        baseline: AgentTrajectory,
        variant: AgentTrajectory,
        *,
        swap_order: bool = False,
    ) -> JudgeVerdict:
        cached = short_circuit_verdict(baseline, variant)
        if cached is not None:
            return cached

        primary = await self._call_judge(task, baseline, variant, baseline_is_first=True)
        primary = enforce_score_parity(primary)

        if not swap_order:
            return primary

        swapped = await self._call_judge(task, variant, baseline, baseline_is_first=False)
        swapped = enforce_score_parity(swapped)

        if primary.winner != swapped.winner:
            return JudgeVerdict(
                winner="tie",
                baseline_score=round((primary.baseline_score + swapped.baseline_score) / 2, 2),
                variant_score=round((primary.variant_score + swapped.variant_score) / 2, 2),
                reasoning=(
                    f"Swap-order bias guard: primary winner={primary.winner}, "
                    f"swapped winner={swapped.winner}. Coerced to tie.\n\n"
                    f"Primary reasoning: {primary.reasoning}\n\n"
                    f"Swapped reasoning: {swapped.reasoning}"
                ),
                tool_regression_detected=(primary.tool_regression_detected or swapped.tool_regression_detected),
                fix_suggestion=primary.fix_suggestion or swapped.fix_suggestion,
            )

        return primary

    async def _call_judge(
        self,
        task: Task,
        first: AgentTrajectory,
        second: AgentTrajectory,
        *,
        baseline_is_first: bool,
    ) -> JudgeVerdict:
        prompt = (
            f"Task ID: {task.id}\n"
            f"Prompt: {task.prompt}\n"
            f"Expected outcome: {task.expected_outcome}\n\n"
            f"{_format_trajectory('baseline', first)}\n\n"
            f"{_format_trajectory('variant', second)}\n\n"
            "Decide which agent performed better. Use winner='baseline', 'variant', or 'tie'. "
            "If the variant loses or tool_regression_detected is true, include a concrete "
            "fix_suggestion that an AI coding agent could apply."
        )
        verdict = await self.backend.judge_verdict(system=JUDGE_SYSTEM, prompt=prompt)
        return self._normalize_verdict(verdict, baseline_is_first=baseline_is_first)

    @staticmethod
    def _normalize_verdict(
        verdict: JudgeVerdict,
        *,
        baseline_is_first: bool,
    ) -> JudgeVerdict:
        """Map judge winner labels back to baseline/variant when order was swapped."""
        if baseline_is_first or verdict.winner == "tie":
            return verdict
        mapped_winner = "variant" if verdict.winner == "baseline" else "baseline"
        return verdict.model_copy(update={"winner": mapped_winner})


# Backwards-compatible alias
GeminiJudge = TrajectoryJudge
