"""
Error tracking utility, backed by the project's own container.
Reads/writes /app/.codesentinel/errors.json INSIDE the project container
via the executor service - no host filesystem involvement at all.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any

from src.executor.sandbox import CodeSandbox


class ErrorTracker:
    MAX_RETRIES = 3
    MAX_TOTAL_ATTEMPTS = 6

    def __init__(self, project: str, language: str = "python", sandbox: CodeSandbox = None):
        self.project = project
        self.language = language
        self.sandbox = sandbox or CodeSandbox()

    def _read(self) -> Dict[str, Any]:
        raw = self.sandbox.read_errors(self.project)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        self.sandbox.write_errors(self.project, self.language, json.dumps(data, indent=4))

    @staticmethod
    def _normalize_error(error_message: str) -> str:
        lines = [l for l in error_message.strip().splitlines() if l.strip()]
        if not lines:
            return error_message.strip().lower()
        return lines[-1].strip().lower()

    @classmethod
    def _hash_error(cls, error_message: str) -> str:
        return hashlib.sha256(cls._normalize_error(error_message).encode()).hexdigest()[:16]

    def log_error(self, error_message: str, traceback: str = "") -> Dict[str, Any]:
        data = self._read()
        error_id = self._hash_error(error_message)

        if error_id in data:
            data[error_id]["count"] += 1
            data[error_id]["last_seen"] = datetime.utcnow().isoformat()
            data[error_id]["traceback"] = traceback
        else:
            data[error_id] = {
                "message": error_message,
                "traceback": traceback,
                "count": 1,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat(),
            }

        self._write(data)
        count = data[error_id]["count"]
        return {"error_id": error_id, "count": count, "max_retries_reached": count >= self.MAX_RETRIES}

    def record_attempt(self) -> Dict[str, Any]:
        data = self._read()
        meta = data.get("_meta", {"total_attempts": 0})
        meta["total_attempts"] += 1
        data["_meta"] = meta
        self._write(data)
        return {
            "total_attempts": meta["total_attempts"],
            "global_limit_reached": meta["total_attempts"] > self.MAX_TOTAL_ATTEMPTS,
        }

    def clear_errors(self) -> None:
        data = self._read()
        meta = data.get("_meta")
        self._write({"_meta": meta} if meta else {})