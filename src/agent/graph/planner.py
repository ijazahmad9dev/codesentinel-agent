"""
Planner logic: plain text completion (no tool-calling), parsed with a
regex. Deliberately avoids structured output / tool calls given how
often complex JSON generation has failed under this project's fallback
model - a numbered list is far more robust to parse and to generate
correctly. Any parsing failure or exception falls back to a single-step
plan, so the planner can never hard-fail the pipeline.
"""

import re

from src.agent.core import build_planner_model
from src.agent.graph.planner_prompt import PLANNER_SYSTEM_PROMPT
from src.utils.model_info import get_model_name


def parse_subtasks(text: str) -> list[str]:
    subtasks = []
    for line in text.strip().splitlines():
        match = re.match(r"^\s*\d+[\.\)]\s*(.+)$", line.strip())
        if match:
            subtasks.append(match.group(1).strip())
    return subtasks


def generate_plan(task: str) -> tuple[list[str], str | None]:
    subtasks: list[str] = []
    model_name = None

    try:
        model = build_planner_model()
        response = model.invoke([
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ])
        subtasks = parse_subtasks(response.content)
        model_name = get_model_name(response)
    except Exception:
        subtasks = []

    if not subtasks:
        subtasks = [task]

    return subtasks, model_name