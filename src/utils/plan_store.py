"""
Persists the generated plan as PLAN.md inside the project's own sandbox
- visible in the project directory alongside the generated code, not
hidden in .codesentinel. Rewritten after each completed step so
checkboxes reflect real progress.
"""

from src.executor.sandbox import CodeSandbox


def render_plan_md(task: str, subtasks: list[str], completed_index: int = -1) -> str:
    lines = ["# Plan", "", f"**Task:** {task}", "", "## Steps", ""]
    for i, step in enumerate(subtasks):
        checked = "x" if i <= completed_index else " "
        lines.append(f"- [{checked}] **{i + 1}.** {step}")
    return "\n".join(lines) + "\n"


def write_plan(
    sandbox: CodeSandbox,
    project: str,
    language: str,
    task: str,
    subtasks: list[str],
    completed_index: int = -1,
) -> None:
    content = render_plan_md(task, subtasks, completed_index)
    sandbox.write_file(project, language, "PLAN.md", content)