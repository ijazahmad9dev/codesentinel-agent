import argparse
from src.agent.core import build_agent
from src.agent import tools as agent_tools
from src.utils.logger import get_logger

logger = get_logger(__name__)


def slugify(text: str) -> str:
    return "-".join(text.lower().split())[:40]


def run(task: str, project: str, language: str):
    agent_tools.set_current_project(project, language)
    agent = build_agent()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"recursion_limit": 25},
    )

    print("\n" + "=" * 60)
    print(f"CODESENTINEL RESULT — project: {project}")
    print(f"Inspect with: docker exec -it codesentinel-proj-{project} sh")
    print("=" * 60)
    print(result["messages"][-1].content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?")
    parser.add_argument("-p", "--project")
    parser.add_argument("-l", "--language", default="python", choices=["python", "node"])
    args = parser.parse_args()

    if args.task:
        project = args.project or slugify(args.task)
        run(args.task, project, args.language)
        return

    print("CodeSentinel — Self-Healing Coding Agent\n")
    while True:
        task = input("Task > ").strip()
        if task.lower() in {"exit", "quit"}:
            break
        if not task:
            continue
        project = input("Project (blank = auto) > ").strip() or slugify(task)
        language = input("Language [python/node] > ").strip() or "python"
        run(task, project, language)


if __name__ == "__main__":
    main()