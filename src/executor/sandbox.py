"""
E2B-backed sandbox client. Same public interface as the previous
Docker-executor client (write_file, run, list_files, read_file,
read_errors, write_errors, cleanup) - everything above this file
(tools.py, error_tracker.py) is unaffected by this migration.

Sandbox identity: E2B sandbox IDs are opaque and generated per creation,
unlike our old container names ("codesentinel-proj-<project>"). A local
mapping file (data/e2b_sandbox_map.json) tracks project -> sandbox_id so
a project can be reconnected to its existing sandbox across separate CLI
invocations, as long as the sandbox hasn't been killed or expired.

Known limitation: E2B sandbox persistence (pause/resume) is public beta
with documented edge cases around filesystem state after multiple resume
cycles. If a sandbox has expired or been killed, we transparently create
a fresh one - meaning a project's files/state can be lost between
sessions if enough time passes. This is an accepted trade-off for now,
not a guarantee we're making.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass

from e2b import Sandbox

from src.config import settings

PROJECT_DIR = "/home/user/project"
META_DIR = "/home/user/.codesentinel"
SANDBOX_MAP_FILE = Path(settings.DATA_DIR) / "e2b_sandbox_map.json"


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int


def _load_map() -> dict:
    if not SANDBOX_MAP_FILE.exists():
        return {}
    try:
        return json.loads(SANDBOX_MAP_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_map(data: dict) -> None:
    SANDBOX_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    SANDBOX_MAP_FILE.write_text(json.dumps(data, indent=2))


class CodeSandbox:
    def __init__(self):
        os.environ.setdefault("E2B_API_KEY", settings.E2B_API_KEY)
        self._sandboxes: dict[str, Sandbox] = {}

    def _ensure_sandbox(self, project: str) -> Sandbox:
        if project in self._sandboxes:
            return self._sandboxes[project]

        mapping = _load_map()
        sandbox_id = mapping.get(project)

        if sandbox_id:
            try:
                sandbox = Sandbox.connect(sandbox_id)
                self._sandboxes[project] = sandbox
                return sandbox
            except Exception:
                # Sandbox expired, was killed, or resume failed - fall
                # through and create a fresh one. Prior state is lost.
                pass

        sandbox = Sandbox.create(timeout=settings.E2B_TIMEOUT_SECONDS)
        sandbox.commands.run(f"mkdir -p {PROJECT_DIR} {META_DIR}")
        mapping[project] = sandbox.sandbox_id
        _save_map(mapping)
        self._sandboxes[project] = sandbox
        return sandbox

    def write_file(self, project: str, language: str, file_path: str, content: str) -> bool:
        sandbox = self._ensure_sandbox(project)
        remote_path = f"{PROJECT_DIR}/{file_path.lstrip('/')}"
        try:
            sandbox.files.write(remote_path, content)
            return True
        except Exception:
            return False

    def read_file(self, project: str, file_path: str) -> str | None:
        sandbox = self._ensure_sandbox(project)
        remote_path = f"{PROJECT_DIR}/{file_path.lstrip('/')}"
        try:
            return sandbox.files.read(remote_path)
        except Exception:
            return None

    def run(self, project: str, language: str, command: str, timeout: int = None) -> ExecutionResult:
        sandbox = self._ensure_sandbox(project)
        try:
            result = sandbox.commands.run(
                command, cwd=PROJECT_DIR, timeout=timeout or settings.EXECUTION_TIMEOUT,
            )
            return ExecutionResult(
                success=result.exit_code == 0,
                stdout=(result.stdout or "").strip(),
                stderr=(result.stderr or "").strip(),
                returncode=result.exit_code,
            )
        except Exception as e:
            return ExecutionResult(success=False, stdout="", stderr=f"Sandbox error: {e}", returncode=-1)

    def list_files(self, project: str) -> list[str]:
        sandbox = self._ensure_sandbox(project)
        try:
            result = sandbox.commands.run(f"find {PROJECT_DIR} -type f")
            return [
                line.replace(PROJECT_DIR + "/", "")
                for line in (result.stdout or "").strip().splitlines() if line.strip()
            ]
        except Exception:
            return []

    def write_errors(self, project: str, language: str, content: str) -> bool:
        sandbox = self._ensure_sandbox(project)
        try:
            sandbox.files.write(f"{META_DIR}/errors.json", content)
            return True
        except Exception:
            return False

    def read_errors(self, project: str) -> str:
        sandbox = self._ensure_sandbox(project)
        try:
            content = sandbox.files.read(f"{META_DIR}/errors.json")
            return content if content else "{}"
        except Exception:
            return "{}"

    def cleanup(self, project: str) -> None:
        mapping = _load_map()
        sandbox_id = mapping.pop(project, None)
        _save_map(mapping)
        if sandbox_id:
            try:
                Sandbox.kill(sandbox_id)
            except Exception:
                pass
        self._sandboxes.pop(project, None)