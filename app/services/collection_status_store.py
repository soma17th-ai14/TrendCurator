"""수집 상태 영속화 스토어."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class CollectionStatusStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def save_collected_at(self, collected_at: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self._load_raw()
        data["last_collected_at"] = collected_at
        self._write(data)

    def load_collected_at(self) -> str | None:
        return self._load_raw().get("last_collected_at")

    def _load_raw(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
