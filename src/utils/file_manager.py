"""
Manages writing agent-generated files to a persistent workspace directory,
with protection against path traversal or absolute-path escapes.
"""

from pathlib import Path

from src.config import settings


class FileManager:
    def __init__(self, workspace_dir: str = None):
        # Always resolve to an absolute path up front, independent of CWD.
        self.workspace_dir = Path(workspace_dir or settings.WORKSPACE_DIR).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def write_file(self, relative_path: str, content: str) -> str:
        candidate = Path(relative_path)

        # Reject absolute paths outright — never let the model dictate one.
        if candidate.is_absolute():
            raise ValueError(
                f"Refusing absolute path: {relative_path}. "
                f"Provide a path relative to the workspace."
            )

        # Reject any attempt to climb out via '..'
        if ".." in candidate.parts:
            raise ValueError(f"Refusing path traversal: {relative_path}")

        target = (self.workspace_dir / candidate).resolve()

        # Final belt-and-suspenders check after resolution.
        if self.workspace_dir not in target.parents and target != self.workspace_dir:
            raise ValueError(f"Refusing to write outside workspace: {relative_path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self.workspace_dir))

    def list_files(self) -> list[str]:
        return [
            str(p.relative_to(self.workspace_dir))
            for p in self.workspace_dir.rglob("*")
            if p.is_file()
        ]