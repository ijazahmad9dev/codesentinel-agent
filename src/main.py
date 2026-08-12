"""
Entry point: run a coding task, or inspect an existing project's
sandbox (files + error log) without running a new task.
"""

import argparse
import json
import re

from langgraph.errors import GraphRecursionError

from src.agent.core import build_agent
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.logger import get_logger
from src.agent.graph.build import build_graph

logger = get_logger(__name__)

NODE_KEYWORDS = [
    "next.js", "nextjs", "next js", "react", "express", "node.js", "nodejs",
    "node js", "javascript", "typescript", "npm", "vue", "svelte",
]


def slugify(text: str) -> str:
    return "-".join(text.lower().split())[:40]


def detect_language(task: str) -> str:
    """
    Infers python vs node from the task text so a non-technical user
    never needs to know or pass --language themselves. Defaults to
    python when nothing node-related is mentioned.
    """
    lowered = task.lower()
    for keyword in NODE_KEYWORDS:
        if keyword in lowered:
            return "node"
    return "python"

def run(task: str, project: str, language: str):

    graph = build_graph()

    initial_state = {
        "task": task, "project": project, "language": language,
        "subtasks": [], "current_index": 0, "results": [],
        "models_used": [], "final_summary": "",
    }

    plan_printed = False
    final_state = initial_state

    try:
        for state in graph.stream(initial_state, config={"recursion_limit": 50}, stream_mode="values"):
            final_state = state
            if not plan_printed and state.get("subtasks"):
                print("\n" + "=" * 60)
                print("Plan")
                print("=" * 60)
                for i, step in enumerate(state["subtasks"], 1):
                    print(f"{i}. {step}")
                print()
                plan_printed = True
    except Exception as e:
        print("\n" + "=" * 60)
        print("Result")
        print("=" * 60)
        print(
            f"Something went wrong while building this: {e}\n"
            f"Anything already built so far is saved - check with: "
            f"python -m src.main --inspect {project}"
        )
        return

    print("=" * 60)
    print("Result")
    print("=" * 60)
    print(final_state["final_summary"])

    models_used = list(dict.fromkeys(final_state["models_used"]))
    print("\n" + "-" * 60)
    if len(models_used) > 1:
        print(f"⚠ Models used: {' → '.join(models_used)} (fallback occurred)")
    elif models_used:
        print(f"Model used: {models_used[0]}")
    else:
        print("Model used: (could not be determined)")
    print("-" * 60)

def inspect(project: str):
    sandbox = CodeSandbox()

    files = sandbox.list_files(project)
    print(f"\n=== Files in project '{project}' ===")
    if not files:
        print("(none found - project may not exist, or its sandbox expired)")
    for f in files:
        print(f"- {f}")

    # for f in files:
    #     content = sandbox.read_file(project, f)
    #     print(f"\n--- {f} ---")
    #     print(content if content is not None else "(could not read)")

    print(f"\n=== Error log ===")
    raw_errors = sandbox.read_errors(project)
    try:
        print(json.dumps(json.loads(raw_errors), indent=2))
    except json.JSONDecodeError:
        print(raw_errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?")
    parser.add_argument("-p", "--project")
    parser.add_argument("-l", "--language", choices=["python", "node"],
                         help="Optional - auto-detected from the task if omitted")
    parser.add_argument("--inspect", metavar="PROJECT")
    args = parser.parse_args()

    if args.inspect:
        inspect(args.inspect)
        return

    if args.task:
        project = args.project or slugify(args.task)
        language = args.language or detect_language(args.task)
        run(args.task, project, language)
        return

    print("CodeSentinel\n")
    while True:
        task = input("What would you like built? > ").strip()
        if task.lower() in {"exit", "quit"}:
            break
        if not task:
            continue
        project = slugify(task)
        language = detect_language(task)
        run(task, project, language)


if __name__ == "__main__":
    main()