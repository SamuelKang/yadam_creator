#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


ROOT = Path(__file__).resolve().parents[3]
STYLE_PREFIX = (
    "Ghibli-inspired hand-drawn 2D animation, painterly illustrated look, "
    "non-photorealistic rendering."
)
STYLE_SUFFIX = (
    "Korean Joseon-era visual details, no on-screen writing."
)


def _project_path(story_id: str) -> Path:
    return ROOT / "work" / story_id / "out" / "project.json"


def _clean_text(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return t
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _apply_style(prompt: str) -> str:
    t = _clean_text(prompt)
    if not t:
        return t

    # Remove duplicate style prefix if already injected.
    t = re.sub(
        r"^\s*Ghibli-inspired hand-drawn 2D animation,\s*painterly illustrated look,\s*non-photorealistic rendering\.\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )

    # Drop verbose style tails from older templates to keep prompt compact.
    t = re.sub(
        r"\s*Ghibli-inspired hand-drawn 2D animation[^.]*\.\s*",
        " ",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\s*No modern objects[^.]*\.\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()

    # Rebuild compact style-locked prompt.
    out = f"{STYLE_PREFIX} {t}"
    if "no on-screen writing" not in out.lower():
        if not out.endswith("."):
            out += "."
        out += f" {STYLE_SUFFIX}"

    return _clean_text(out)


def _process_project(project: Dict[str, Any], apply: bool) -> Tuple[int, int]:
    changed = 0
    missing = 0
    scenes = project.get("scenes") or []
    if not isinstance(scenes, list):
        return 0, 0

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for key in ("llm_clip_prompt",):
            old = str(scene.get(key) or "")
            if not old:
                continue
            has_style = "ghibli-inspired" in old.lower() and "non-photorealistic" in old.lower()
            if not has_style:
                missing += 1
            new = _apply_style(old)
            if apply and new != old:
                scene[key] = new
                changed += 1

        img = scene.get("image")
        if isinstance(img, dict):
            old2 = str(img.get("prompt_used") or "")
            if old2:
                has_style2 = "ghibli-inspired" in old2.lower() and "non-photorealistic" in old2.lower()
                if not has_style2:
                    missing += 1
                new2 = _apply_style(old2)
                if apply and new2 != old2:
                    img["prompt_used"] = new2
                    changed += 1
    return changed, missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Enforce compact Flow style lock on scene prompts.")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = _project_path(args.story_id)
    if not path.exists():
        print(f"FAIL: missing project.json: {path}")
        return 2

    project = json.loads(path.read_text(encoding="utf-8"))
    changed, missing = _process_project(project, apply=args.apply)

    if args.apply:
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"APPLIED: style_lock changed={changed}, previously_missing={missing}")
        return 0

    if missing == 0:
        print("OK: style_lock_present")
        return 0
    print(f"FOUND: style_lock_missing={missing}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
