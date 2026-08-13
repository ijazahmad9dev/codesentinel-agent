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
import re
import bisect
from typing import Optional


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

class EditFileInput(BaseModel):
    file_path: str = Field(...)
    old_str: str = Field(..., description="Exact string (default) or regex pattern (if use_regex=True) to find.")
    new_str: str = Field(..., description="Replacement text. If use_regex, backreferences like \\1 are supported.")
    use_regex: bool = Field(
        default=False,
        description="If True, treat old_str as a regex pattern (re.MULTILINE) instead of a literal string."
    )
    line_start: Optional[int] = Field(
        default=None,
        description="1-indexed line number to restrict the search to (inclusive). Optional."
    )
    line_end: Optional[int] = Field(
        default=None,
        description="1-indexed line number to restrict the search to (inclusive). Optional."
    )


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


def _line_offsets(text: str):
    """offsets[i] = char offset where line (i+1) starts. Last entry = len(text)."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return offsets, len(lines)


def _offset_to_line(offsets: list, char_offset: int) -> int:
    """Map an absolute char offset back to a 1-indexed line number."""
    i = bisect.bisect_right(offsets, char_offset) - 1
    i = max(0, min(i, len(offsets) - 2))
    return i + 1


def _resolve_char_range(offsets, total_lines, line_start, line_end):
    """Clamp/resolve the optional line range to a (start_char, end_char) slice."""
    ls = max(1, line_start) if line_start else 1
    le = min(total_lines, line_end) if line_end else total_lines
    if ls > le:
        ls, le = le, ls
    ls = min(ls, total_lines)
    le = max(le, ls)
    start_char = offsets[ls - 1]
    end_char = offsets[le]
    return start_char, end_char, ls, le


@tool("edit_code_in_file", args_schema=EditFileInput)
def edit_code_in_file(
    file_path: str,
    old_str: str,
    new_str: str,
    use_regex: bool = False,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> str:
    """
    Make a targeted, SMALL edit to an existing file. Prefer this over
    write_code_to_file when fixing a specific bug - rewriting the whole
    file risks changing unrelated code. If the fix requires changing more
    than a few lines, use write_code_to_file for a full rewrite instead
    of trying to force it through this tool.

    By default old_str is matched as an exact literal string. Set
    use_regex=True to match old_str as a regex pattern instead (re.MULTILINE).
    In either mode, the target must match exactly once - use line_start/
    line_end (1-indexed, inclusive) to disambiguate when it appears more
    than once in the file.
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

    offsets, total_lines = _line_offsets(current)

    if (line_start is not None or line_end is not None) and total_lines == 0:
        return f"EDIT_FAILED: {file_path} is empty; line_start/line_end cannot be applied."

    start_char, end_char, resolved_start, resolved_end = _resolve_char_range(
        offsets, max(total_lines, 1), line_start, line_end
    )
    region = current[start_char:end_char]
    range_note = (
        f" (restricted to lines {resolved_start}-{resolved_end})"
        if (line_start is not None or line_end is not None)
        else ""
    )

    if use_regex:
        try:
            pattern = re.compile(old_str, re.MULTILINE)
        except re.error as e:
            return f"EDIT_FAILED: invalid regex in old_str: {e}"

        matches = list(pattern.finditer(region))
        if not matches:
            return (
                f"EDIT_FAILED: regex pattern found no matches in {file_path}{range_note}. "
                f"Use view_file to check current content, or broaden/adjust line_start/line_end."
            )
        if len(matches) > 1:
            line_nos = sorted({_offset_to_line(offsets, start_char + m.start()) for m in matches})
            return (
                f"EDIT_FAILED: regex pattern matched {len(matches)} times in {file_path}{range_note} "
                f"(lines: {', '.join(str(n) for n in line_nos)}). "
                f"Narrow the pattern or set line_start/line_end to target one match."
            )

        updated_region, _ = pattern.subn(new_str, region, count=1)
        updated = current[:start_char] + updated_region + current[end_char:]
    else:
        count = region.count(old_str)
        if count == 0:
            near_misses = _find_near_misses(current, old_str)
            return (
                f"EDIT_FAILED: old_str not found in {file_path}{range_note}. "
                f"Re-check exact text - whitespace and indentation matter. "
                f"Use view_file to see exact current content with line numbers."
                f"{near_misses}"
            )
        if count > 1:
            line_nos = []
            search_from = 0
            for _ in range(count):
                idx = region.index(old_str, search_from)
                line_nos.append(_offset_to_line(offsets, start_char + idx))
                search_from = idx + 1
            return (
                f"EDIT_FAILED: old_str appears {count} times in {file_path}{range_note} "
                f"(lines: {', '.join(str(n) for n in line_nos)}). "
                f"Include more surrounding context, or set line_start/line_end to target one occurrence."
            )

        idx = region.index(old_str)
        abs_start = start_char + idx
        abs_end = abs_start + len(old_str)
        updated = current[:abs_start] + new_str + current[abs_end:]

    if _current_language == "python":
        try:
            check_code_safety(updated)
        except SafetyViolation as e:
            logger.warning(f"Refused unsafe edit: {e.reason}")
            return f"REFUSED: {e.reason}"

    ok = sandbox.write_file(_current_project, _current_language, file_path, updated)
    if ok:
        tracker.clear_errors()
        logger.info(f"edit_code_in_file: {file_path} (regex={use_regex})")
        return f"FILE_EDITED: {file_path}"
    return f"FILE_EDIT_FAILED: {file_path}"