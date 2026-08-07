"""
CodeSentinel Executor Service.

Two execution modes:
  /execute          - single-file snippet, stdin-piped, network-isolated.
                       Fast path for simple scripts (Python or Node).
  /execute_project  - full multi-file project (already saved to disk by
                       the main app), copied into a fresh container and
                       run with a real command (e.g. npm install && npm
                       run build). Requires network access for dependency
                       installation, so isolation is intentionally looser
                       here than in single-file mode.

This service is the ONLY component with Docker socket access - the main
agent app never touches it directly.
"""

import base64
import io
import shutil
import subprocess
import tarfile
import tempfile
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CodeSentinel Executor")

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "single_file_cmd": ["python3", "-"],
    },
    "node": {
        "image": "node:20-slim",
        "single_file_cmd": ["node", "-"],
    },
}

DEFAULT_SINGLE_TIMEOUT = 15
DEFAULT_PROJECT_TIMEOUT = 120


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = DEFAULT_SINGLE_TIMEOUT


class ExecuteProjectRequest(BaseModel):
    language: str
    command: str
    files_tar_b64: str  # base64-encoded tar of the project directory
    timeout: int = DEFAULT_PROJECT_TIMEOUT


class ExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    returncode: int


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
    config = LANGUAGE_CONFIG.get(req.language)
    if not config:
        return ExecuteResponse(
            success=False, stdout="",
            stderr=f"Unsupported language: {req.language}. Supported: {list(LANGUAGE_CONFIG)}",
            returncode=-1,
        )

    container_name = f"codesentinel-exec-{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker", "run", "--rm", "-i",
        "--name", container_name,
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--pids-limit", "64",
        "--memory", "256m",
        "--memory-swap", "256m",
        "--cpus", "0.5",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        config["image"],
        *config["single_file_cmd"],
    ]

    try:
        result = subprocess.run(
            cmd, input=req.code, capture_output=True, text=True, timeout=req.timeout,
        )
        return ExecuteResponse(
            success=result.returncode == 0,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        return ExecuteResponse(
            success=False, stdout="",
            stderr=f"Execution timed out after {req.timeout} seconds.",
            returncode=-1,
        )


@app.post("/execute_project", response_model=ExecuteResponse)
def execute_project(req: ExecuteProjectRequest):
    config = LANGUAGE_CONFIG.get(req.language)
    if not config:
        return ExecuteResponse(
            success=False, stdout="",
            stderr=f"Unsupported language: {req.language}. Supported: {list(LANGUAGE_CONFIG)}",
            returncode=-1,
        )

    container_name = f"codesentinel-proj-{uuid.uuid4().hex[:12]}"
    scratch_dir = tempfile.mkdtemp(prefix="cs-project-")

    try:
        tar_bytes = base64.b64decode(req.files_tar_b64)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            tar.extractall(scratch_dir)

        subprocess.run(
            [
                "docker", "create",
                "--name", container_name,
                "--pids-limit", "256",
                "--memory", "512m",
                "--memory-swap", "512m",
                "--cpus", "1.0",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "-w", "/app/project",
                config["image"],
                "sh", "-c", req.command,
            ],
            capture_output=True, text=True, check=True, timeout=15,
        )

        subprocess.run(
            ["docker", "cp", f"{scratch_dir}/.", f"{container_name}:/app/project"],
            capture_output=True, text=True, check=True, timeout=30,
        )

        result = subprocess.run(
            ["docker", "start", "-a", container_name],
            capture_output=True, text=True, timeout=req.timeout,
        )

        inspect = subprocess.run(
            ["docker", "inspect", container_name, "--format", "{{.State.ExitCode}}"],
            capture_output=True, text=True,
        )
        exit_code = int(inspect.stdout.strip() or "-1")

        return ExecuteResponse(
            success=exit_code == 0,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            returncode=exit_code,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        return ExecuteResponse(
            success=False, stdout="",
            stderr=f"Execution timed out after {req.timeout} seconds.",
            returncode=-1,
        )
    except subprocess.CalledProcessError as e:
        return ExecuteResponse(
            success=False, stdout="", stderr=f"Setup failed: {e.stderr}", returncode=-1,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        shutil.rmtree(scratch_dir, ignore_errors=True)


@app.get("/health")
def health():
    return {"status": "ok"}