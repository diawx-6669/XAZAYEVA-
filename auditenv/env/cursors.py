"""Opaque, stable pagination cursors: HMAC(episode key, episode_id|table|offset).

The key is derived from the episode's public content, so the same episode always yields
the same cursors, and a cursor from another episode (or another table) does not verify.
"""

import base64
import hashlib
import hmac


class CursorCodec:
    def __init__(self, episode_id: str, content_digest: str):
        self.episode_id = episode_id
        self.key = hashlib.sha256(f"auditenv-cursor|{episode_id}|{content_digest}".encode()).digest()

    def _mac(self, table: str, offset: int) -> bytes:
        msg = f"{self.episode_id}|{table}|{offset}".encode()
        return hmac.new(self.key, msg, hashlib.sha256).digest()[:12]

    def encode(self, table: str, offset: int) -> str:
        raw = offset.to_bytes(4, "big") + self._mac(table, offset)
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def decode(self, table: str, token) -> int | None:
        if not isinstance(token, str) or not (1 <= len(token) <= 64):
            return None
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        except (ValueError, TypeError):
            return None
        if len(raw) != 16:
            return None
        offset = int.from_bytes(raw[:4], "big")
        if not hmac.compare_digest(raw[4:], self._mac(table, offset)):
            return None
        return offset
