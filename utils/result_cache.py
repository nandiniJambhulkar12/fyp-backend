"""In-memory cache for analysis results."""

import hashlib
import json
from typing import Optional, Dict, Any
from time import time


class AnalysisResultCache:
    """Simple in-memory cache for analysis results with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _hash_code(code: str) -> str:
        """Generate SHA256 hash of code."""
        return hashlib.sha256(code.encode()).hexdigest()

    def get(self, code: str) -> Optional[Any]:
        """
        Get cached analysis result.

        Args:
            code: Source code

        Returns:
            Cached result or None if not found/expired
        """
        key = self._hash_code(code)
        entry = self.cache.get(key)

        if not entry:
            return None

        # Check if expired
        if time() - entry['timestamp'] > self.ttl_seconds:
            del self.cache[key]
            return None

        return entry['result']

    def set(self, code: str, result: Any) -> None:
        """
        Cache analysis result.

        Args:
            code: Source code
            result: Analysis result to cache
        """
        key = self._hash_code(code)
        self.cache[key] = {
            'result': result,
            'timestamp': time(),
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = time()
        valid_entries = sum(
            1 for entry in self.cache.values()
            if now - entry['timestamp'] <= self.ttl_seconds
        )

        return {
            'total_entries': len(self.cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self.cache) - valid_entries,
        }
