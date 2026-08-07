"""
LangChain tool definitions exposed to the agent.
"""

from langchain_core.tools import tool

from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.file_manager import FileManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

sandbox = CodeSandbox()
tracker = ErrorTracker()
file_manager = FileManager()


@tool
def execute_python_code(code: str) -> str:
    """
    Execute the given Python code in an isolated sandbox and return the result.
    Use this to test or verify code before saving it permanently.
    """
    logger.info("Executing generated code.")
    result = sandbox.run(code)

    if result.success:
        return f"EXECUTION_SUCCESS\nSTDOUT:\n{result.stdout}"

    return (
        f"EXECUTION_FAILED\n"
        f"RETURN_CODE: {result.returncode}\n"
        f"STDERR:\n{result.stderr}"
    )


@tool
def write_code_to_file(file_path: str, code: str) -> str:
    """
    Save code to a real file inside the project workspace.
    Use this ONLY after the code has been verified working via
    execute_python_code. Use a meaningful relative path and filename,
    e.g. "reverse_string.py", or for multi-file projects like a FastAPI
    backend: "app/main.py", "app/models.py", "app/routers/users.py".
    Call this once per file for multi-file projects.
    """
    try:
        saved_path = file_manager.write_file(file_path, code)
        logger.info(f"Saved file: {saved_path}")
        return f"FILE_SAVED: {saved_path}"
    except ValueError as e:
        return f"FILE_SAVE_FAILED: {e}"


@tool
def log_execution_error(error_message: str, traceback: str = "") -> str:
    """
    Log an execution error to the persistent JSON error store.
    Call this whenever execute_python_code returns EXECUTION_FAILED.
    Returns the occurrence count for this exact error and whether the
    3-attempt retry limit has been reached.
    """
    result = tracker.log_error(error_message, traceback)
    logger.warning(f"Error logged: {result}")

    if result["max_retries_reached"]:
        return (
            f"MAX_RETRIES_REACHED. This exact error has occurred "
            f"{result['count']} times. STOP fixing and report this to the user."
        )
    return f"ERROR_LOGGED. Occurrence count: {result['count']} / 3."


@tool
def clear_execution_error(error_message: str) -> str:
    """
    Remove an error from the persistent JSON error store once it has been
    successfully resolved (i.e. execute_python_code returned EXECUTION_SUCCESS
    after a fix for a previously logged error).
    """
    removed = tracker.clear_error(error_message)
    if removed:
        return "ERROR_CLEARED from log."
    return "No matching error found in log."