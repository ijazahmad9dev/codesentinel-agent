"""
Entry point: run a coding task, or inspect an existing project's
sandbox (files + error log) without running a new task.
"""

import argparse
import json

from src.agent.graph.build import build_graph
from src.config import settings
from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.logger import get_logger

logger = get_logger(__name__)

NODE_KEYWORDS = [
    "next.js", "nextjs", "next js", "react", "express", "node.js", "nodejs",
    "node js", "javascript", "typescript", "npm", "vue", "svelte",
]

NODE_LABELS = {
    "planner": "Planner",
    "coding_agent": "Coding Agent",
    "tester": "Tester",
    "fix_from_tests": "Coding Agent (fixing test failure)",
    "reviewer": "Reviewer",
    "fix_from_review": "Coding Agent (fixing review finding)",
    "final_aggregate": "Finalizing",
}


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


def get_total_attempts(project: str, language: str) -> int:
    tracker = ErrorTracker(project, language, CodeSandbox())
    return tracker._read().get("_meta", {}).get("total_attempts", 0)


def run(task: str, project: str, language: str):
    graph = build_graph()

    initial_state = {
        "task": task, "project": project, "language": language,
        "subtasks": [], "current_index": 0, "results": [],
        "models_used": [], "final_summary": "",
        "test_status": "pending", "test_output": "", "test_round": 0,
        "review_status": "pending", "review_output": "", "review_round": 0,
    }

    state = dict(initial_state)
    plan_printed = False

    try:
        for update in graph.stream(initial_state, config={"recursion_limit": 60}, stream_mode="updates"):
            for node_name, node_update in update.items():
                state.update(node_update)

                label = NODE_LABELS.get(node_name, node_name)
                progress = ""
                if node_name == "coding_agent":
                    progress = f" [step {state['current_index']}/{len(state['subtasks'])}]"
                elif node_name == "tester":
                    progress = f" [round {state['test_round']}]"
                elif node_name == "reviewer":
                    progress = f" [round {state['review_round']}]"

                total_attempts = get_total_attempts(project, language)
                print(f"→ [{label}]{progress}  (total attempts so far: {total_attempts})")

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

    print("\n" + "=" * 60)
    print("Result")
    print("=" * 60)

    total_attempts = get_total_attempts(project, language)
    if total_attempts >= settings.MAX_AGENT_ITERATIONS:
        completed = state["current_index"]
        planned = len(state["subtasks"])
        print(
            f"⚠ STOPPED: reached the maximum attempt limit "
            f"({total_attempts}/{settings.MAX_AGENT_ITERATIONS} attempts).\n"
            f"Completed {completed} of {planned} planned steps before stopping.\n"
        )

    print(state["final_summary"])
    print(f"\nTests: {state['test_status']}  |  Review: {state['review_status']}")

    models_used = list(dict.fromkeys(state["models_used"]))
    print("\n" + "-" * 60)
    if len(models_used) > 1:
        print(f"⚠ Models used: {' → '.join(models_used)} (fallback occurred)")
    elif models_used:
        print(f"Model used: {models_used[0]}")
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