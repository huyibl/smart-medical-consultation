#!/usr/bin/env python3
"""入口：python main.py probe|ingest|search|ask|serve。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from smc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
