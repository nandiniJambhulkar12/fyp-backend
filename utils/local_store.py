import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional

from models import HistoryEntry, UserProfile


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalJSONStore:
    def __init__(self, users_path: Path, history_path: Path) -> None:
        self.users_path = users_path
        self.history_path = history_path
        self._lock = threading.Lock()
        self.users: Dict[str, dict] = self._load_json(users_path, default={})
        self.history: List[dict] = self._load_json(history_path, default=[])

    def register_user(self, email: str, name: str, firebase_uid: Optional[str] = None) -> UserProfile:
        with self._lock:
            existing = self.users.get(email.lower())
            if existing:
                if name:
                    existing["name"] = name
                if firebase_uid:
                    existing["firebase_uid"] = firebase_uid
                existing["updated_at"] = utc_now_iso()
                self._persist_users()
                return UserProfile(**existing)

            now = utc_now_iso()
            profile = {
                "id": str(uuid.uuid4()),
                "name": name or email.split("@")[0],
                "email": email,
                "phone": None,
                "verified": True,
                "active": True,
                "role": "user",
                "firebase_uid": firebase_uid,
                "created_at": now,
                "updated_at": now,
            }
            self.users[email.lower()] = profile
            self._persist_users()
            return UserProfile(**profile)

    def get_user(self, email: str) -> Optional[UserProfile]:
        with self._lock:
            user = self.users.get(email.lower())
            return UserProfile(**user) if user else None

    def update_user(self, email: str, name: str, phone: Optional[str]) -> UserProfile:
        with self._lock:
            user = self.users.get(email.lower())
            if not user:
                raise KeyError("User not found")
            user["name"] = name
            user["phone"] = phone or None
            user["updated_at"] = utc_now_iso()
            self._persist_users()
            return UserProfile(**user)

    def add_history(
        self,
        user_email: str,
        file_name: str,
        language: str,
        risk_level: str,
        vulnerability_detected: bool,
        findings: List[dict],
    ) -> HistoryEntry:
        with self._lock:
            entry = HistoryEntry(
                id=str(uuid.uuid4()),
                user_email=user_email,
                file_name=file_name,
                language=language,
                risk_level=risk_level,
                vulnerability_count=len(findings),
                vulnerability_detected=vulnerability_detected,
                analysis_date=utc_now_iso(),
                findings=findings,
            )
            self.history.insert(0, entry.dict())
            self._persist_history()
            return entry

    def list_history(self, user_email: str) -> List[HistoryEntry]:
        with self._lock:
            return [
                HistoryEntry(**entry)
                for entry in self.history
                if entry.get("user_email", "").lower() == user_email.lower()
            ]

    def delete_history(self, user_email: str, entry_id: str) -> bool:
        with self._lock:
            before = len(self.history)
            self.history = [
                entry
                for entry in self.history
                if not (
                    entry.get("user_email", "").lower() == user_email.lower()
                    and entry.get("id") == entry_id
                )
            ]
            deleted = len(self.history) != before
            if deleted:
                self._persist_history()
            return deleted

    @staticmethod
    def _load_json(path: Path, default):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _persist_users(self) -> None:
        self._atomic_write(self.users_path, self.users)

    def _persist_history(self) -> None:
        self._atomic_write(self.history_path, self.history)

    @staticmethod
    def _atomic_write(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file)
            temp_path = Path(tmp_file.name)
        temp_path.replace(path)