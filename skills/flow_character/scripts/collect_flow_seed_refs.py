#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "flow_scene" / "scripts" / "collect_flow_seed_refs.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")

