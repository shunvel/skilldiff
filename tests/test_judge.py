"""Tests for judge guards and verdict normalization."""

from skilldiff.judge import (
    GeminiJudge,
    enforce_score_parity,
    short_circuit_verdict,
)
from skilldiff.models import AgentTrajectory, JudgeVerdict


def _trajectory(
    agent_id: str,
    *,
    final_output: str = "answer",
    total_steps: int = 1,
) -> AgentTrajectory:
    return AgentTrajectory(
        agent_id=agent_id,
        steps=[],
        final_output=final_output,
        total_steps=total_steps,
        execution_time_sec=0.5,
    )


def test_short_circuit_on_identical_output_and_steps() -> None:
    baseline = _trajectory("baseline", final_output="same", total_steps=2)
    variant = _trajectory("variant", final_output="same", total_steps=2)
    verdict = short_circuit_verdict(baseline, variant)
    assert verdict is not None
    assert verdict.winner == "tie"
    assert verdict.baseline_score == 5.0
    assert verdict.variant_score == 5.0


def test_short_circuit_skips_when_output_differs() -> None:
    baseline = _trajectory("baseline", final_output="a")
    variant = _trajectory("variant", final_output="b")
    assert short_circuit_verdict(baseline, variant) is None


def test_short_circuit_skips_when_step_count_differs() -> None:
    baseline = _trajectory("baseline", final_output="same", total_steps=1)
    variant = _trajectory("variant", final_output="same", total_steps=2)
    assert short_circuit_verdict(baseline, variant) is None


def test_enforce_score_parity_coerces_invalid_variant_win() -> None:
    verdict = JudgeVerdict(
        winner="variant",
        baseline_score=8.0,
        variant_score=7.5,
        reasoning="initial",
        tool_regression_detected=False,
    )
    fixed = enforce_score_parity(verdict)
    assert fixed.winner == "tie"
    assert "Score parity guard" in fixed.reasoning


def test_enforce_score_parity_allows_valid_variant_win() -> None:
    verdict = JudgeVerdict(
        winner="variant",
        baseline_score=6.0,
        variant_score=8.0,
        reasoning="valid",
        tool_regression_detected=False,
    )
    assert enforce_score_parity(verdict).winner == "variant"


def test_normalize_verdict_maps_swapped_baseline_win_to_variant() -> None:
    verdict = JudgeVerdict(
        winner="baseline",
        baseline_score=7.0,
        variant_score=5.0,
        reasoning="first agent won",
        tool_regression_detected=False,
    )
    mapped = GeminiJudge._normalize_verdict(verdict, baseline_is_first=False)
    assert mapped.winner == "variant"


def test_normalize_verdict_keeps_tie() -> None:
    verdict = JudgeVerdict(
        winner="tie",
        baseline_score=5.0,
        variant_score=5.0,
        reasoning="even",
        tool_regression_detected=False,
    )
    mapped = GeminiJudge._normalize_verdict(verdict, baseline_is_first=False)
    assert mapped.winner == "tie"
