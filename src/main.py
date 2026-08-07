"""
Entry point: accepts a natural language coding task, plus an optional
project name to namespace generated files under, and runs the
self-healing agent.
"""

import argparse

from src.agent.core import build_agent
from src.agent import tools as agent_tools
from src.utils.logger import get_logger

logger = get_logger(__name__)


def slugify(text: str) -> str:
    return "-".join(text.lower().split())[:40]


def extract_saved_files(messages) -> list[str]:
    saved = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for call in tool_calls:
            if call.get("name") == "write_code_to_file":
                path = call.get("args", {}).get("file_path")
                if path:
                    saved.append(path)
    return saved


from langgraph.errors import GraphRecursionError

def run(task: str, project: str):
    agent_tools.set_current_project(project)
    agent = build_agent()

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": task}]},
            config={"recursion_limit": 25},
        )
    except GraphRecursionError:
        print("\n" + "=" * 60)
        print(f"CODESENTINEL RESULT — project: {project}")
        print("=" * 60)
        print(
            "The agent exceeded its step budget without reaching a stable "
            "result. This usually means it kept trying different broken "
            "approaches without converging — check the task's clarity, or "
            "review data/<project>/errors.json for what it attempted."
        )
        return


def main():
    parser = argparse.ArgumentParser(description="CodeSentinel coding agent")
    parser.add_argument("task", nargs="?", help="Natural language coding task")
    parser.add_argument(
        "-p", "--project",
        help="Project name to namespace generated files under. "
             "Auto-generated from the task if omitted.",
    )
    args = parser.parse_args()

    if args.task:
        project = args.project or slugify(args.task)
        run(args.task, project)
        return

    print("CodeSentinel — Self-Healing Coding Agent")
    print("Type 'exit' to quit.\n")

    while True:
        task = input("Task > ").strip()
        if task.lower() in {"exit", "quit"}:
            break
        if not task:
            continue
        project_input = input("Project name (blank = auto) > ").strip()
        project = project_input or slugify(task)
        run(task, project)


if __name__ == "__main__":
    main()