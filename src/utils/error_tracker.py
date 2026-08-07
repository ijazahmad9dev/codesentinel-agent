"""
Error tracking utility, scoped per project.
Each project gets its own data/<project>/errors.json, created on first
failure. Enforces the "3 strikes" rule automatically, from inside the
execution tools themselves - not dependent on the model calling a
separate logging tool.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.config import settings


class ErrorTracker:
    MAX_RETRIES = 3
    MAX_TOTAL_ATTEMPTS = 6  # hard cap, independent of whether errors repeat

    def _meta_key(self):
        return "_meta"

    def record_attempt(self) -> dict:
        """
        Increments a hard, unconditional attempt counter for this project -
        independent of whether individual errors repeat. This is the real
        backstop: even if the model tries a different broken approach every
        time (so no single error hash ever hits 3), total attempts still
        gets capped.
        """
        data = self._read()
        meta = data.get(self._meta_key(), {"total_attempts": 0})
        meta["total_attempts"] += 1
        data[self._meta_key()] = meta
        self._write(data)
        return {
            "total_attempts": meta["total_attempts"],
            "global_limit_reached": meta["total_attempts"] > self.MAX_TOTAL_ATTEMPTS,
        }

    def clear_all(self) -> None:
        self._write({})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.error_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.error_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def _hash_error(error_message: str) -> str:
        normalized = error_message.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

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
        return {
            "error_id": error_id,
            "count": count,
            "max_retries_reached": count >= self.MAX_RETRIES,
        }

    @staticmethod
    def _normalize_error(error_message: str) -> str:
        """
        Extract a stable signature from a traceback - the final
        'ExceptionType: message' line - rather than the full text, so
        the same root-cause error across slightly different code attempts
        still counts as the same error for the retry cap.
        """
        lines = [l for l in error_message.strip().splitlines() if l.strip()]
        if not lines:
            return error_message.strip().lower()
        return lines[-1].strip().lower()

    @staticmethod
    def _hash_error(error_message: str) -> str:
        normalized = ErrorTracker._normalize_error(error_message)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]