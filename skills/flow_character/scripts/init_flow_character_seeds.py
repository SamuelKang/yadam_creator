#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "flow_scene" / "scripts" / "init_flow_new_project_with_char_seeds.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")

