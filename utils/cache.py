import json
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time
from typing import Dict, Optional, Tuple


class AnalysisCache:
    def __init__(self, cache_path: Path, ttl_seconds: int) -> None:
        self.cache_path = cache_path
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, object]] = {}
        self._load()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time() - float(entry["timestamp"]) > self.ttl_seconds:
                self._cache.pop(key, None)
                self._persist()
                return None
            return dict(entry["value"])

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._cache[key] = {"timestamp": time(), "value": value}
            self._persist()

    def _load(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.cache_path.exists():
            return
        try:
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._cache = {}

    def _persist(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=str(self.cache_path.parent), encoding="utf-8") as tmp_file:
            json.dump(self._cache, tmp_file)
            temp_path = Path(tmp_file.name)
        temp_path.replace(self.cache_path)


class CooldownLimiter:
    def __init__(self, cooldown_seconds: int) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._last_seen: Dict[str, float] = {}

    def allow(self, key: str) -> Tuple[bool, float]:
        now = time()
        with self._lock:
            last_seen = self._last_seen.get(key)
            if last_seen is not None:
                elapsed = now - last_seen
                if elapsed < self.cooldown_seconds:
                    return False, round(self.cooldown_seconds - elapsed, 1)
            self._last_seen[key] = now
            return True, 0.0