"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from skilldiff.models import JudgeVerdict, Task


def test_task_defaults_sanity_tag() -> None:
    task = Task(id="t1", prompt="do thing", expected_outcome="done")
    assert task.tags == ["sanity"]


def test_judge_verdict_score_bounds() -> None:
    JudgeVerdict(
        winner="variant",
        baseline_score=0.0,
        variant_score=10.0,
        reasoning="ok",
        tool_regression_detected=False,
    )
    with pytest.raises(ValidationError):
        JudgeVerdict(
            winner="variant",
            baseline_score=-1.0,
            variant_score=5.0,
            reasoning="bad",
            tool_regression_detected=False,
        )
    with pytest.raises(ValidationError):
        JudgeVerdict(
            winner="variant",
            baseline_score=5.0,
            variant_score=11.0,
            reasoning="bad",
            tool_regression_detected=False,
        )


def test_judge_verdict_invalid_winner() -> None:
    with pytest.raises(ValidationError):
        JudgeVerdict.model_validate(
            {
                "winner": "other",
                "baseline_score": 5.0,
                "variant_score": 5.0,
                "reasoning": "x",
                "tool_regression_detected": False,
            }
        )
