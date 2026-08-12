"""
LangChain tool definitions exposed to the agent.
"""

from langchain_core.tools import tool

from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.code_safety import check_code_safety, SafetyViolation
from src.utils.logger import get_logger
from pydantic import BaseModel, Field
import difflib

logger = get_logger(__name__)

sandbox = CodeSandbox()

_current_project = "default"
_current_language = "python"

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

class WriteFileInput(BaseModel):
    file_path: str = Field(
        ...,
        description="REQUIRED. The relative path to save this file at, e.g. 'src/App.jsx', 'package.json'. Never omit this field.",
    )
    code: str = Field(
        ...,
        description="The full file content to write.",
    )

class EditFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path of the file to edit.")
    old_str: str = Field(
        ...,
        max_length=500,
        description=(
            "The EXACT existing text to replace - must match the file "
            "character-for-character and appear exactly once. Keep this "
            "SHORT and TARGETED (a few lines at most) - just enough "
            "surrounding context to make it unique. Do NOT pass large "
            "blocks of code here; larger exact-match strings are far more "
            "likely to fail on a whitespace mismatch, and large arguments "
            "are more likely to cause tool-call generation errors. If the "
            "change is large or spans much of the file, use "
            "write_code_to_file instead."
        ),
    )
    new_str: str = Field(..., max_length=500, description="The replacement text.")

def _find_near_misses(current: str, old_str: str) -> str:
    file_lines = current.splitlines()
    target_line = old_str.splitlines()[0] if old_str.splitlines() else old_str
    matches = difflib.get_close_matches(target_line, file_lines, n=3, cutoff=0.6)
    if not matches:
        return ""
    hints = []
    for m in matches:
        line_no = file_lines.index(m) + 1
        hints.append(f"  line {line_no}: {m}")
    return "\nClosest similar lines found:\n" + "\n".join(hints)

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


# @tool
# def write_code_to_file(file_path: str, code: str) -> str:
#     """
#     Save a file into this project's dedicated container. Give a path
#     relative to the project root, e.g. "main.py", "app/models.py",
#     "package.json". Prefer multiple small, purpose-specific files over one
#     large file - see the modular code guidance in your instructions.
#     """
#     if _current_language == "python":
#         try:
#             check_code_safety(code)
#         except SafetyViolation as e:
#             logger.warning(f"Refused unsafe file write: {e.reason}")
#             return f"REFUSED: {e.reason}"

#     ok = sandbox.write_file(_current_project, _current_language, file_path, code)
#     if ok:
#         logger.info(f"write_code_to_file: {file_path}")
#         return f"FILE_SAVED: {file_path} (container: codesentinel-proj-{_current_project})"
#     return f"FILE_SAVE_FAILED: {file_path}"

@tool("write_code_to_file", args_schema=WriteFileInput)
def write_code_to_file(file_path: str, code: str) -> str:
    """
    Save a file into this project's dedicated container. Give a path
    relative to the project root, e.g. "main.py", "app/models.py",
    "package.json". Prefer multiple small, purpose-specific files over one
    large file - see the modular code guidance in your instructions.
    """
    tracker = _tracker()
    attempt = tracker.record_attempt()
    if attempt["global_limit_reached"]:
        return (
            f"GLOBAL_ATTEMPT_LIMIT_REACHED: {attempt['total_attempts']} attempts "
            f"made without success (limit: {tracker.max_total_attempts}). "
            f"STOP and report this to the user."
        )

    if _current_language == "python":
        try:
            check_code_safety(code)
        except SafetyViolation as e:
            logger.warning(f"Refused unsafe file write: {e.reason}")
            return f"REFUSED: {e.reason}"

    ok = sandbox.write_file(_current_project, _current_language, file_path, code)
    if ok:
        tracker.clear_errors()
        logger.info(f"write_code_to_file: {file_path}")
        return f"FILE_SAVED: {file_path}"
    return f"FILE_SAVE_FAILED: {file_path}"

@tool
def view_file(file_path: str) -> str:
    """
    View a file's content with line numbers, to help construct an exact
    old_str for edit_code_in_file. Prefer this over running 'cat' or
    'sed' via execute_project_command when you need to read a file
    before editing it.
    """
    content = sandbox.read_file(_current_project, file_path)
    if content is None:
        return f"VIEW_FAILED: {file_path} does not exist."
    lines = content.splitlines()
    numbered = "\n".join(f"{i+1:4}| {line}" for i, line in enumerate(lines))
    return numbered


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

@tool("edit_code_in_file", args_schema=EditFileInput)
def edit_code_in_file(file_path: str, old_str: str, new_str: str) -> str:
    """
    Make a targeted, SMALL edit to an existing file. Prefer this over
    write_code_to_file when fixing a specific bug - rewriting the whole
    file risks changing unrelated code. If the fix requires changing more
    than a few lines, use write_code_to_file for a full rewrite instead
    of trying to force it through this tool.
    """
    tracker = _tracker()
    attempt = tracker.record_attempt()
    if attempt["global_limit_reached"]:
        return (
            f"GLOBAL_ATTEMPT_LIMIT_REACHED: {attempt['total_attempts']} attempts "
            f"made without success (limit: {tracker.max_total_attempts}). "
            f"STOP and report this to the user."
        )

    current = sandbox.read_file(_current_project, file_path)
    if current is None:
        return f"EDIT_FAILED: {file_path} does not exist yet. Use write_code_to_file to create it."

    count = current.count(old_str)
    count = current.count(old_str)
    if count == 0:
        near_misses = _find_near_misses(current, old_str)
        return (
            f"EDIT_FAILED: old_str not found in {file_path}. "
            f"Re-check exact text - whitespace and indentation matter. "
            f"Use view_file to see exact current content with line numbers."
            f"{near_misses}"
        )
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
        tracker.clear_errors()
        logger.info(f"edit_code_in_file: {file_path}")
        return f"FILE_EDITED: {file_path}"
    return f"FILE_EDIT_FAILED: {file_path}"