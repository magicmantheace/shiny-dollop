"""Compatibility import for Crawl's shared deterministic variety selector."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from livingworld.attack_variety import *  # noqa: F401,F403,E402
