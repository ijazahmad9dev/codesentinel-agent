"""
CodeSentinel Executor Service — persistent per-project containers.

Each project gets ONE long-lived container. /app/project holds the
agent's code files; /app/.codesentinel holds internal state (currently
just errors.json) - kept separate so error logs never appear mixed in
with the actual generated code.
"""

import logging
import subprocess

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("executor")

app = FastAPI(title="CodeSentinel Executor")

LANGUAGE_CONFIG = {
    "python": {"image": "codesentinel-runner-python:latest"},
    "node": {"image": "codesentinel-runner-node:latest"},
}

PROJECT_DIR = "/app/project"
META_DIR = "/app/.codesentinel"
CONTAINER_PREFIX = "codesentinel-proj-"
CONTAINER_UID = "1000"
CONTAINER_GID = "1000"


def container_name(project: str) -> str:
    return f"{CONTAINER_PREFIX}{project}"


def container_exists(name: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "-a", "-q", "-f", f"name=^{name}$"],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def container_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{name}$"],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def ensure_container(project: str, language: str) -> str:
    name = container_name(project)
    config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

    if container_exists(name):
        if not container_running(name):
            subprocess.run(["docker", "start", name], capture_output=True, text=True)
        return name

    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", name,
            "--pids-limit", "256",
            "--memory", "512m",
            "--memory-swap", "512m",
            "--cpus", "1.0",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", f"{CONTAINER_UID}:{CONTAINER_GID}",
            "-w", PROJECT_DIR,
            config["image"],
            "sh", "-c", "tail -f /dev/null",
        ],
        capture_output=True, text=True, check=True,
    )
    return name


def write_text_to_container(name: str, remote_path: str, content: str) -> dict:
    """
    Generic write helper - as UID 1000, no docker cp/chown needed since
    both PROJECT_DIR and META_DIR are pre-owned by 1000 at image build time.
    """
    remote_dir = "/".join(remote_path.split("/")[:-1])

    mkdir_result = subprocess.run(
        ["docker", "exec", "--user", f"{CONTAINER_UID}:{CONTAINER_GID}",
         name, "mkdir", "-p", remote_dir],
        capture_output=True, text=True,
    )
    if mkdir_result.returncode != 0:
        return {"success": False, "stderr": f"mkdir failed: {mkdir_result.stderr}"}

    write_result = subprocess.run(
        ["docker", "exec", "-i", "--user", f"{CONTAINER_UID}:{CONTAINER_GID}",
         name, "sh", "-c", f"cat > {remote_path}"],
        input=content, capture_output=True, text=True,
    )
    if write_result.returncode != 0:
        return {"success": False, "stderr": f"write failed: {write_result.stderr}"}

    return {"success": True, "stderr": ""}


def read_text_from_container(name: str, remote_path: str) -> str | None:
    result = subprocess.run(
        ["docker", "exec", name, "sh", "-c", f"cat {remote_path} 2>/dev/null"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


class WriteFileRequest(BaseModel):
    project: str
    language: str = "python"
    file_path: str
    content: str


class ExecRequest(BaseModel):
    project: str
    language: str = "python"
    command: str
    timeout: int = 60


class ExecResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    returncode: int


class ErrorsWriteRequest(BaseModel):
    project: str
    language: str = "python"
    content: str


@app.post("/project/write_file")
def write_file(req: WriteFileRequest):
    name = ensure_container(req.project, req.language)
    rel_path = req.file_path.lstrip("/")
    remote_path = f"{PROJECT_DIR}/{rel_path}"

    result = write_text_to_container(name, remote_path, req.content)
    logger.info(f"write_file {remote_path} -> success={result['success']}")
    return {"success": result["success"], "path": rel_path, "stderr": result["stderr"]}


@app.post("/project/exec", response_model=ExecResponse)
def exec_in_project(req: ExecRequest):
    name = ensure_container(req.project, req.language)

    try:
        result = subprocess.run(
            ["docker", "exec", "--user", f"{CONTAINER_UID}:{CONTAINER_GID}",
             "-w", PROJECT_DIR, name, "sh", "-c", req.command],
            capture_output=True, text=True, timeout=req.timeout,
        )
        return ExecResponse(
            success=result.returncode == 0,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ExecResponse(
            success=False, stdout="",
            stderr=f"Command timed out after {req.timeout}s.",
            returncode=-1,
        )


@app.post("/project/errors/write")
def write_errors(req: ErrorsWriteRequest):
    name = ensure_container(req.project, req.language)
    remote_path = f"{META_DIR}/errors.json"
    result = write_text_to_container(name, remote_path, req.content)
    return {"success": result["success"], "stderr": result["stderr"]}


@app.get("/project/{project}/errors")
def read_errors(project: str):
    name = container_name(project)
    if not container_exists(name):
        return {"content": "{}"}
    if not container_running(name):
        subprocess.run(["docker", "start", name], capture_output=True, text=True)
    content = read_text_from_container(name, f"{META_DIR}/errors.json")
    return {"content": content if content else "{}"}

@app.get("/project/{project}/file")
def read_file(project: str, path: str):
    name = container_name(project)
    if not container_exists(name):
        return {"content": None}
    if not container_running(name):
        subprocess.run(["docker", "start", name], capture_output=True, text=True)
    remote_path = f"{PROJECT_DIR}/{path.lstrip('/')}"
    content = read_text_from_container(name, remote_path)
    return {"content": content}

@app.get("/project/{project}/files")
def list_files(project: str):
    name = container_name(project)
    if not container_exists(name):
        return {"files": []}
    if not container_running(name):
        subprocess.run(["docker", "start", name], capture_output=True, text=True)
    result = subprocess.run(
        ["docker", "exec", name, "find", PROJECT_DIR, "-type", "f"],
        capture_output=True, text=True,
    )
    files = [
        line.replace(PROJECT_DIR + "/", "")
        for line in result.stdout.strip().splitlines() if line.strip()
    ]
    return {"files": files, "container": name}


@app.delete("/project/{project}")
def delete_project(project: str):
    subprocess.run(["docker", "rm", "-f", container_name(project)], capture_output=True, text=True)
    return {"deleted": container_name(project)}


@app.get("/health")
def health():
    return {"status": "ok"}