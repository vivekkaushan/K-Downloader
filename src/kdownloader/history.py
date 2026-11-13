"""Download history (JSON file, newest first)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import paths
from .config import atomic_write_json


class HistoryStore:
    def __init__(self, path: Path | None = None, max_items: int = 500):
        self.path = Path(path) if path else paths.app_home() / "history.json"
        self.max_items = max_items
        self._lock = threading.Lock()
        self._items: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = []
            self._items = [d for d in data if isinstance(d, dict) and d.get("id")] if isinstance(data, list) else []

    def _save(self) -> None:
        atomic_write_json(self.path, self._items)

    def add(self, record: Dict[str, Any]) -> Dict[str, Any]:
        rec = dict(record)
        rec.setdefault("id", uuid.uuid4().hex)
        rec.setdefault("finished_at", datetime.now().isoformat(timespec="seconds"))
        with self._lock:
            self._items.insert(0, rec)
            del self._items[self.max_items:]
            self._save()
        return rec

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._items)

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return next((r for r in self._items if r["id"] == record_id), None)

    def remove(self, record_id: str) -> None:
        with self._lock:
            self._items = [r for r in self._items if r["id"] != record_id]
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._save()

    def set_max(self, max_items: int) -> None:
        with self._lock:
            self.max_items = max_items
            del self._items[max_items:]
            self._save()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            done = [r for r in self._items if r.get("status") == "Completed"]
            return {
                "completed": len(done),
                "failed": sum(1 for r in self._items if r.get("status") == "Failed"),
                "bytes": sum(int(r.get("size") or 0) for r in done),
            }
