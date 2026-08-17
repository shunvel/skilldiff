"""Dynamic tool loading and async agent execution."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from skilldiff.llm import (
    LLMBackend,
    append_assistant_message,
    append_tool_result,
)
from skilldiff.models import AgentTrajectory, Task, TrajectoryStep
from skilldiff.tools_schema import ToolSpec, build_tool_specs, load_tools_from_script

DEFAULT_MAX_STEPS = 16
QUICK_MAX_STEPS = 8


def _serialize_args(args: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(args, default=str))


class SimpleAgentRunner:
    """Runs baseline and variant agents concurrently against a task."""

    def __init__(
        self,
        backend: LLMBackend,
        baseline_tools_path: Path,
        variant_tools_path: Path,
        *,
        quick: bool = False,
    ) -> None:
        self.backend = backend
        self.baseline_tools = load_tools_from_script(baseline_tools_path)
        self.variant_tools = load_tools_from_script(variant_tools_path)
        self.baseline_specs = build_tool_specs(self.baseline_tools)
        self.variant_specs = build_tool_specs(self.variant_tools)
        self.max_steps = QUICK_MAX_STEPS if quick else DEFAULT_MAX_STEPS

    async def run_pair(self, task: Task) -> tuple[AgentTrajectory, AgentTrajectory]:
        baseline, variant = await asyncio.gather(
            self._run_agent(
                agent_id="baseline",
                task=task,
                tools=self.baseline_tools,
                tool_specs=self.baseline_specs,
            ),
            self._run_agent(
                agent_id="variant",
                task=task,
                tools=self.variant_tools,
                tool_specs=self.variant_specs,
            ),
        )
        return baseline, variant

    async def _run_agent(
        self,
        *,
        agent_id: str,
        task: Task,
        tools: dict[str, Callable[..., Any]],
        tool_specs: list[ToolSpec],
    ) -> AgentTrajectory:
        started = time.perf_counter()
        steps: list[TrajectoryStep] = []
        error: Optional[str] = None
        final_output = ""

        system_instruction = (
            "You are an autonomous agent. Use available tools when needed, "
            "then provide a concise final answer that satisfies the task."
        )
        user_prompt = (
            f"Task: {task.prompt}\n\n"
            f"Expected outcome: {task.expected_outcome}\n\n"
            "Complete the task using tools if helpful, then respond with the final answer."
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

        try:
            for step_number in range(1, self.max_steps + 1):
                turn = await self.backend.agent_turn(
                    system=system_instruction,
                    messages=messages,
                    tools=tool_specs,
                    temperature=0.2,
                )

                if not turn.tool_calls:
                    final_output = turn.text
                    steps.append(
                        TrajectoryStep(
                            step_number=step_number,
                            thought=turn.text,
                            observation=None,
                        )
                    )
                    break

                append_assistant_message(messages, turn)

                for call in turn.tool_calls:
                    tool_name = call.name
                    tool_args = _serialize_args(call.args)
                    if tool_name not in tools:
                        observation = f"Error: tool `{tool_name}` is not available."
                    else:
                        try:
                            result = tools[tool_name](**tool_args)
                            if inspect.isawaitable(result):
                                result = await result
                            observation = str(result)
                        except Exception as exc:  # noqa: BLE001
                            observation = f"Tool error in `{tool_name}`: {exc}"

                    steps.append(
                        TrajectoryStep(
                            step_number=step_number,
                            thought=turn.text,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            observation=observation,
                        )
                    )
                    append_tool_result(messages, name=tool_name, content=observation)
            else:
                final_output = turn.text if "turn" in locals() else ""
                if not final_output:
                    final_output = "Agent reached max steps without a final answer."
                error = "max_steps_reached"
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            if not final_output:
                final_output = f"Agent failed: {exc}"

        elapsed = time.perf_counter() - started
        return AgentTrajectory(
            agent_id=agent_id,
            steps=steps,
            final_output=final_output,
            total_steps=len(steps),
            execution_time_sec=round(elapsed, 3),
            error=error,
        )
