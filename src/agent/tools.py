"""
LangChain tool definitions exposed to the agent.
"""

from langchain_core.tools import tool

from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.code_safety import check_code_safety, SafetyViolation
from src.utils.logger import get_logger

logger = get_logger(__name__)

sandbox = CodeSandbox()

_current_project = "default"
_current_language = "python"

from pydantic import BaseModel, Field


class ExecuteCommandInput(BaseModel):
    command: str = Field(
        ...,
        max_length=200,
        description=(
            "A SINGLE-LINE shell command only - no newlines, no heredocs (<<), "
            "no embedded multi-step Python scripts. Examples: 'python3 main.py', "
            "'pip install -r requirements.txt && python3 main.py'. "
            "To run anything more complex, save it to a file with "
            "write_code_to_file first, then call this with a short command "
            "to run that file, e.g. 'python3 verify_server.py'."
        ),
    )

def _is_overly_complex_command(command: str) -> str | None:
    """
    Returns a rejection reason if the command looks like an inline
    multi-line script rather than a simple shell command - these are
    prone to malformed JSON tool-call generation regardless of model.
    Returns None if the command is fine.
    """
    if "<<" in command and ("'PY'" in command or '"PY"' in command or "<<PY" in command):
        return "heredoc-style inline script"
    if command.count("\n") > 3:
        return f"too many lines ({command.count(chr(10))}) for an inline command"
    if len(command) > 300:
        return f"too long ({len(command)} chars) for an inline command"
    return None

def set_current_project(project_slug: str, language: str = "python") -> None:
    global _current_project, _current_language
    _current_project = project_slug
    _current_language = language


def _tracker() -> ErrorTracker:
    return ErrorTracker(_current_project, _current_language, sandbox)


@tool
def write_code_to_file(file_path: str, code: str) -> str:
    """
    Save a file into this project's dedicated container. Give a path
    relative to the project root, e.g. "main.py", "app/models.py",
    "package.json". Prefer multiple small, purpose-specific files over one
    large file - see the modular code guidance in your instructions.
    """
    if _current_language == "python":
        try:
            check_code_safety(code)
        except SafetyViolation as e:
            logger.warning(f"Refused unsafe file write: {e.reason}")
            return f"REFUSED: {e.reason}"

    ok = sandbox.write_file(_current_project, _current_language, file_path, code)
    if ok:
        logger.info(f"write_code_to_file: {file_path}")
        return f"FILE_SAVED: {file_path} (container: codesentinel-proj-{_current_project})"
    return f"FILE_SAVE_FAILED: {file_path}"



@tool("execute_project_command", args_schema=ExecuteCommandInput)
def execute_project_command(command: str) -> str:
    """
    Run a simple shell command inside this project's container.
    """
    complexity_issue = _is_overly_complex_command(command)
    if complexity_issue:
        return (
            f"REJECTED: command looks like {complexity_issue}. "
            f"Write this logic to a file with write_code_to_file instead, "
            f"then call this tool with a short command to run that file."
        )

    tracker = _tracker()
    attempt = tracker.record_attempt()
    if attempt["global_limit_reached"]:
        return (
            f"GLOBAL_ATTEMPT_LIMIT_REACHED: {attempt['total_attempts']} attempts "
            f"made without success (limit: {tracker.max_total_attempts}). "
            f"STOP and report this to the user."
        )

    logger.info(f"execute_project_command [{_current_project}]: {command}")
    result = sandbox.run(_current_project, _current_language, command)

    if result.success:
        tracker.clear_errors()
        return f"EXECUTION_SUCCESS\nSTDOUT:\n{result.stdout}"

    log_result = tracker.log_error(result.stderr or "unknown error")
    if log_result["max_retries_reached"]:
        return (
            f"EXECUTION_FAILED (attempt {log_result['count']}/3)\nSTDERR:\n{result.stderr}\n\n"
            f"MAX_RETRIES_REACHED: STOP retrying and report this failure to the user."
        )
    return f"EXECUTION_FAILED (attempt {log_result['count']}/3)\nSTDERR:\n{result.stderr}"

@tool
def list_project_files() -> str:
    """List every file currently saved in this project's container."""
    files = sandbox.list_files(_current_project)
    if not files:
        return "No files in this project's container yet."
    return "Files:\n" + "\n".join(f"- {f}" for f in files)

@tool
def edit_code_in_file(file_path: str, old_str: str, new_str: str) -> str:
    """
    Make a targeted edit to an existing file: replaces old_str with
    new_str. old_str must match the file's current content EXACTLY
    (including whitespace) and appear exactly once - this prevents
    accidentally editing the wrong location. Include enough surrounding
    context in old_str to make it unique if needed.

    Prefer this over write_code_to_file when fixing a specific bug in an
    existing file - rewriting the whole file risks changing unrelated
    code that was already working.
    """
    current = sandbox.read_file(_current_project, file_path)
    if current is None:
        return f"EDIT_FAILED: {file_path} does not exist yet. Use write_code_to_file to create it."

    count = current.count(old_str)
    if count == 0:
        return f"EDIT_FAILED: old_str not found in {file_path}. Re-check exact text - whitespace and indentation matter."
    if count > 1:
        return f"EDIT_FAILED: old_str appears {count} times in {file_path}. Include more surrounding context to make it uniquely identify one location."

    updated = current.replace(old_str, new_str, 1)

    if _current_language == "python":
        try:
            check_code_safety(updated)
        except SafetyViolation as e:
            logger.warning(f"Refused unsafe edit: {e.reason}")
            return f"REFUSED: {e.reason}"

    ok = sandbox.write_file(_current_project, _current_language, file_path, updated)
    if ok:
        logger.info(f"edit_code_in_file: {file_path}")
        return f"FILE_EDITED: {file_path}"
    return f"FILE_EDIT_FAILED: {file_path}"