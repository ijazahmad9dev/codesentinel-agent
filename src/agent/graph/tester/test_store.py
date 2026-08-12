from datetime import datetime

from src.executor.sandbox import CodeSandbox


def render_tests_md(round_num: int, status: str, output: str) -> str:
    lines = [
        "# Test Results",
        "",
        f"**Round:** {round_num}",
        f"**Status:** {'✅ PASSED' if status == 'passed' else '❌ FAILED'}",
        f"**Last run:** {datetime.utcnow().isoformat()}Z",
        "",
        "## Output",
        "",
        "```",
        output.strip()[-4000:],  # keep the file readable, tail of output is usually what matters
        "```",
    ]
    return "\n".join(lines) + "\n"


def write_test_results(
    sandbox: CodeSandbox, project: str, language: str, round_num: int, status: str, output: str,
) -> None:
    content = render_tests_md(round_num, status, output)
    sandbox.write_file(project, language, "TESTS.md", content)