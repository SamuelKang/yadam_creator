#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "make_vrew" / "scripts" / "check_post_step8_prompt_gate.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
