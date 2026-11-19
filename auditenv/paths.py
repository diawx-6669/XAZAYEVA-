"""Repository paths (schemas and configs live at the repo root)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT / "schemas"
CONFIGS_DIR = ROOT / "configs"
EPISODES_DIR = ROOT / "episodes"
