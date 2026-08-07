"""
Code execution sandbox.
Executes Python code in an isolated subprocess with a timeout,
running inside the workspace directory so it can import already-saved
project files (e.g. testing main.py against models.py).
"""

import subprocess
import sys
import tempfile
import os
from dataclasses import dataclass

from src.config import settings


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int


class CodeSandbox:
    def __init__(self, timeout: int = None, workspace_dir: str = None):
        self.timeout = timeout or settings.EXECUTION_TIMEOUT
        self.workspace_dir = workspace_dir or settings.WORKSPACE_DIR
        os.makedirs(self.workspace_dir, exist_ok=True)

    def run(self, code: str) -> ExecutionResult:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8",
            dir=self.workspace_dir,
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            process = subprocess.run(
                [sys.executable, os.path.basename(tmp_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workspace_dir,
            )
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=process.stdout.strip(),
                stderr=process.stderr.strip(),
                returncode=process.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout} seconds.",
                returncode=-1,
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass