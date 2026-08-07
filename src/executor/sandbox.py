"""
Client for the CodeSentinel Executor service.
"""

import base64
import io
import tarfile
from dataclasses import dataclass
from pathlib import Path

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

    def run(self, code: str, language: str = "python") -> ExecutionResult:
        try:
            response = requests.post(
                f"{self.executor_url}/execute",
                json={"code": code, "language": language, "timeout": self.timeout},
                timeout=self.timeout + 10,
            )
            response.raise_for_status()
            data = response.json()
            return ExecutionResult(**data)
        except requests.RequestException as e:
            return ExecutionResult(
                success=False, stdout="",
                stderr=f"Executor service unreachable: {e}", returncode=-1,
            )

    def run_project(
        self, project_dir: Path, language: str, command: str, timeout: int = 120
    ) -> ExecutionResult:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            tar.add(project_dir, arcname=".")
        tar_b64 = base64.b64encode(buffer.getvalue()).decode()

        try:
            response = requests.post(
                f"{self.executor_url}/execute_project",
                json={
                    "language": language,
                    "command": command,
                    "files_tar_b64": tar_b64,
                    "timeout": timeout,
                },
                timeout=timeout + 30,
            )
            response.raise_for_status()
            data = response.json()
            return ExecutionResult(**data)
        except requests.RequestException as e:
            return ExecutionResult(
                success=False, stdout="",
                stderr=f"Executor service unreachable: {e}", returncode=-1,
            )