"""
LangChain tool definitions exposed to the agent.
"""

from langchain_core.tools import tool

from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.file_manager import FileManager
from src.utils.code_safety import check_code_safety, SafetyViolation
from src.utils.logger import get_logger

logger = get_logger(__name__)

sandbox = CodeSandbox()
file_manager = FileManager()

_current_project = "default"


def set_current_project(project_slug: str) -> None:
    global _current_project
    _current_project = project_slug


def _tracker() -> ErrorTracker:
    # Instantiated per-call so each project gets its own errors.json,
    # created lazily on first failure during execution.
    return ErrorTracker(_current_project)


@tool
def execute_code(code: str, language: str = "python") -> str:
    """..."""
    tracker = _tracker()
    attempt = tracker.record_attempt()
    if attempt["global_limit_reached"]:
        return (
            f"GLOBAL_ATTEMPT_LIMIT_REACHED: This project has made "
            f"{attempt['total_attempts']} execution attempts without "
            f"succeeding. STOP immediately - do not call execute_code or "
            f"execute_project_command again. Report this failure to the user."
        )

    if language == "python":
        try:
            check_code_safety(code)
        except SafetyViolation as e:
            logger.warning(f"Refused unsafe code: {e.reason}")
            return f"REFUSED: {e.reason} This task is outside the sandbox's allowed scope."

    logger.info(f"Executing {language} snippet in sandbox.")
    result = sandbox.run(code, language=language)

    if result.success:
        tracker.clear_all()
        return f"EXECUTION_SUCCESS\nSTDOUT:\n{result.stdout}"

    log_result = tracker.log_error(result.stderr or "unknown error")
    if log_result["max_retries_reached"]:
        return (
            f"EXECUTION_FAILED (attempt {log_result['count']}/3)\n"
            f"STDERR:\n{result.stderr}\n\n"
            f"MAX_RETRIES_REACHED: This exact error has occurred "
            f"{log_result['count']} times. STOP retrying and report this "
            f"failure to the user."
        )

    return (
        f"EXECUTION_FAILED (attempt {log_result['count']}/3)\n"
        f"RETURN_CODE: {result.returncode}\n"
        f"STDERR:\n{result.stderr}"
    )

@tool
def execute_project_command(command: str, language: str = "python") -> str:
    """
    Run a shell command against the full set of files already saved for
    the current project via write_code_to_file (e.g. "npm install && npm
    run build", "pip install -r requirements.txt && python3 main.py").
    """
    project_path = file_manager.workspace_dir / _current_project
    if not project_path.exists():
        return (
            f"EXECUTION_FAILED\nSTDERR:\nNo files found for project "
            f"'{_current_project}'. Save files with write_code_to_file first."
        )

    logger.info(f"Running project command for '{_current_project}': {command}")
    result = sandbox.run_project(project_path, language=language, command=command)
    tracker = _tracker()

    if result.success:
        tracker.clear_all()
        return f"EXECUTION_SUCCESS\nSTDOUT:\n{result.stdout}"

    log_result = tracker.log_error(result.stderr or "unknown error")
    if log_result["max_retries_reached"]:
        return (
            f"EXECUTION_FAILED (attempt {log_result['count']}/3)\n"
            f"STDERR:\n{result.stderr}\n\n"
            f"MAX_RETRIES_REACHED: This exact error has occurred "
            f"{log_result['count']} times for this project. STOP retrying "
            f"and report this failure to the user."
        )

    return (
        f"EXECUTION_FAILED (attempt {log_result['count']}/3)\n"
        f"RETURN_CODE: {result.returncode}\n"
        f"STDERR:\n{result.stderr}"
    )

@tool
def write_code_to_file(file_path: str, code: str) -> str:
    """..."""
    logger.info(f"write_code_to_file called: {file_path}")
    namespaced_path = f"{_current_project}/{file_path}"
    try:
        saved_path = file_manager.write_file(namespaced_path, code)
        logger.info(f"Saved file: {saved_path}")
        return f"FILE_SAVED: {saved_path}"
    except ValueError as e:
        return f"FILE_SAVE_FAILED: {e}"


@tool
def list_workspace_projects() -> str:
    """..."""
    logger.info("list_workspace_projects called")
    projects = file_manager.list_projects()
    if not projects:
        return "No existing projects in workspace."
    return "Existing projects:\n" + "\n".join(f"- {p}" for p in projects)