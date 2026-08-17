"""Pydantic data models for skilldiff."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    id: str
    prompt: str
    expected_outcome: str
    tags: list[str] = Field(default_factory=lambda: ["sanity"])


class TrajectoryStep(BaseModel):
    step_number: int
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    observation: Optional[str] = None


class AgentTrajectory(BaseModel):
    agent_id: str
    steps: list[TrajectoryStep]
    final_output: str
    total_steps: int
    execution_time_sec: float
    error: Optional[str] = None


class JudgeVerdict(BaseModel):
    winner: Literal["baseline", "variant", "tie"]
    baseline_score: float = Field(ge=0.0, le=10.0)
    variant_score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    tool_regression_detected: bool
    fix_suggestion: Optional[str] = None


class TaskDiffResult(BaseModel):
    task_id: str
    prompt: str
    baseline_trajectory: AgentTrajectory
    variant_trajectory: AgentTrajectory
    verdict: JudgeVerdict
    step_delta: int


class RunSummary(BaseModel):
    total_tasks: int
    variant_wins: int
    variant_losses: int
    ties: int
    win_rate_pct: float


class RunReport(BaseModel):
    timestamp: datetime
    results: list[TaskDiffResult]
    summary: RunSummary
    quick_mode: bool = False
    swap_order: bool = False
