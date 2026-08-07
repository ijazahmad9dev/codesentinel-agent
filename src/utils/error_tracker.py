"""
Error tracking utility.
Maintains a JSON-based log of execution errors, enforces the
"3 strikes" rule, and clears resolved errors.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.config import settings


class ErrorTracker:
    MAX_RETRIES = 3

    def __init__(self, error_file: str = None):
        self.error_file = Path(error_file or settings.ERROR_LOG_PATH)
        self.error_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.error_file.exists():
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

    def clear_error(self, error_message: str) -> bool:
        data = self._read()
        error_id = self._hash_error(error_message)
        if error_id in data:
            del data[error_id]
            self._write(data)
            return True
        return False

    def get_count(self, error_message: str) -> int:
        data = self._read()
        error_id = self._hash_error(error_message)
        return data.get(error_id, {}).get("count", 0)