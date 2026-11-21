"""Write THIRD_PARTY_NOTICES.md from requirements.txt + vendor/wheels METADATA (auditenv/supply.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auditenv.supply import NOTICES_PATH, render_notices  # noqa: E402

if __name__ == "__main__":
    NOTICES_PATH.write_text(render_notices(), "utf-8")
    print(f"third_party: wrote {NOTICES_PATH.name}")
