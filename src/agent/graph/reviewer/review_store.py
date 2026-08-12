from datetime import datetime

from src.executor.sandbox import CodeSandbox


def render_review_md(round_num: int, status: str, output: str) -> str:
    lines = [
        "# Review",
        "",
        f"**Round:** {round_num}",
        f"**Status:** {'✅ PASSED' if status == 'passed' else '❌ FAILED'}",
        f"**Last reviewed:** {datetime.utcnow().isoformat()}Z",
        "",
        "## Notes",
        "",
        output.strip(),
    ]
    return "\n".join(lines) + "\n"


def write_review_results(sandbox: CodeSandbox, project: str, language: str, round_num: int, status: str, output: str) -> None:
    content = render_review_md(round_num, status, output)
    sandbox.write_file(project, language, "REVIEW.md", content)