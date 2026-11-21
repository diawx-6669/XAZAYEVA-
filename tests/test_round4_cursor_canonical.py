"""fix (round 4, found by the black-box jury simulation re-run): a cursor is accepted only in its canonical
form. Before, base64 decoding ignored the unused low bits of the last character and silently dropped
characters outside the alphabet, so e.g. "...4A" -> "...4B" decoded to the same bytes and was accepted -
the jury's "tampered cursor -> invalid_cursor" check failed for about a quarter of the salts."""

import base64

from auditenv.env.cursors import CursorCodec
from auditenv.env.env import AuditEnv
from auditenv.generator.episode import generate_episode

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def test_every_single_character_change_is_rejected():
    codec = CursorCodec("ep-test", "digest")
    for table in ("ledger", "fx"):
        for offset in (50, 100, 250):
            cur = codec.encode(table, offset)
            assert codec.decode(table, cur) == offset
            for i in range(len(cur)):
                for ch in ALPHABET:
                    if ch != cur[i]:
                        bad = cur[:i] + ch + cur[i + 1:]
                        assert codec.decode(table, bad) is None, (cur, bad)


def test_non_canonical_spellings_are_rejected():
    codec = CursorCodec("ep-test", "digest")
    cur = codec.encode("ledger", 50)
    raw = base64.urlsafe_b64decode(cur + "==")
    assert base64.urlsafe_b64encode(raw).decode().rstrip("=") == cur
    for bad in (cur + "==", cur[:5] + "!" + cur[5:], " " + cur, cur + "\n", cur.replace("-", "+").replace("_", "/")
                if ("-" in cur or "_" in cur) else cur + "A"):
        assert codec.decode("ledger", bad) is None, bad


def test_env_rejects_last_char_padding_tamper():
    env = AuditEnv(mode="train")
    env.reset(episode=generate_episode(7, "dev-mixed"))
    cur = env.step({"tool": "list_records", "args": {"table": "ledger", "limit": 10}})[0]["result"]["next_cursor"]
    # flip only the unused low bits of the last character: same decoded bytes as before the fix
    last = ALPHABET.index(cur[-1])
    twin = cur[:-1] + ALPHABET[last ^ 1]
    obs = env.step({"tool": "list_records", "args": {"table": "ledger", "cursor": twin}})[0]
    assert obs.get("error") == {"code": "invalid_cursor"}
    ok = env.step({"tool": "list_records", "args": {"table": "ledger", "cursor": cur}})[0]
    assert "result" in ok
