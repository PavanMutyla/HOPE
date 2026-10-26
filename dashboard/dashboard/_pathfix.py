"""Reflex runs this app from dashboard/ as its CWD, but the shared board
lives in the HOPE repo root's `memory`/`settings` packages one level up.
Import this first (its only job is the sys.path side effect) so `import
settings` / `import memory.board...` resolve regardless of CWD.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
