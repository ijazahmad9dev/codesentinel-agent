import re

from src.agent.core import build_planner_model
from src.agent.graph.planner.prompt import PLANNER_SYSTEM_PROMPT
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