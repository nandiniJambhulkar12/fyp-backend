import base64
import hashlib
import hmac
import json
from typing import Any, Dict


class TokenManager:
    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key.encode("utf-8")

    def issue_token(self, payload: Dict[str, Any]) -> str:
        payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
        signature = hmac.new(self.secret_key, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload_b64}.{signature}"

    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            payload_b64, provided_signature = token.split(".", 1)
        except ValueError as exc:
            raise ValueError("Invalid token format") from exc

        expected_signature = hmac.new(
            self.secret_key,
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("Invalid token signature")

        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(f"{payload_b64}{padding}".encode("utf-8"))
        return json.loads(payload_json.decode("utf-8"))