"""
Entry point: accepts a natural language coding task either as a CLI
argument (single-shot) or via an interactive loop, and runs the
self-healing agent.
"""

import sys

from src.agent.core import build_agent
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_saved_files(messages) -> list[str]:
    """
    Walk the message history and collect every file path the agent
    saved via write_code_to_file.
    """
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


def run(task: str):
    agent = build_agent()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"recursion_limit": 50},
    )

    messages = result["messages"]
    final_message = messages[-1]
    saved_files = extract_saved_files(messages)

    print("\n" + "=" * 60)
    print("CODESENTINEL RESULT")
    print("=" * 60)

    if saved_files:
        print("\nFiles saved to ./workspace:")
        for f in saved_files:
            print(f"  - {f}")
        print()

    print(final_message.content)


def main():
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        run(task)
        return

    print("CodeSentinel — Self-Healing Coding Agent")
    print("Type 'exit' to quit.\n")

    while True:
        task = input("Task > ").strip()
        if task.lower() in {"exit", "quit"}:
            break
        if not task:
            continue
        run(task)


if __name__ == "__main__":
    main()