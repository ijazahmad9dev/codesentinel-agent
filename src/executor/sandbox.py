"""
Client for the CodeSentinel Executor service.
"""

from dataclasses import dataclass
import requests

from src.config import settings


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int


class CodeSandbox:
    def __init__(self, executor_url: str = None, timeout: int = None):
        self.executor_url = executor_url or settings.EXECUTOR_URL
        self.timeout = timeout or settings.EXECUTION_TIMEOUT

    def write_file(self, project: str, language: str, file_path: str, content: str) -> bool:
        response = requests.post(
            f"{self.executor_url}/project/write_file",
            json={"project": project, "language": language, "file_path": file_path, "content": content},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("success", False)

    def run(self, project: str, language: str, command: str, timeout: int = None) -> ExecutionResult:
        try:
            response = requests.post(
                f"{self.executor_url}/project/exec",
                json={"project": project, "language": language, "command": command, "timeout": timeout or self.timeout},
                timeout=(timeout or self.timeout) + 15,
            )
            response.raise_for_status()
            return ExecutionResult(**response.json())
        except requests.RequestException as e:
            return ExecutionResult(success=False, stdout="", stderr=f"Executor service unreachable: {e}", returncode=-1)

    def list_files(self, project: str) -> list[str]:
        response = requests.get(f"{self.executor_url}/project/{project}/files", timeout=15)
        response.raise_for_status()
        return response.json().get("files", [])

    def write_errors(self, project: str, language: str, content: str) -> bool:
        response = requests.post(
            f"{self.executor_url}/project/errors/write",
            json={"project": project, "language": language, "content": content},
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("success", False)

    def read_errors(self, project: str) -> str:
        response = requests.get(f"{self.executor_url}/project/{project}/errors", timeout=15)
        response.raise_for_status()
        return response.json().get("content", "{}")

    def cleanup(self, project: str) -> None:
        requests.delete(f"{self.executor_url}/project/{project}", timeout=15)