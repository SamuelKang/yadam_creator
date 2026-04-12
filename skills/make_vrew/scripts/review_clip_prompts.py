#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[3]

GENERIC_PROMPT_PATTERNS = (
    re.compile(r"^wide shot,\s*joseon-era dramatic scene,\s*korean faces,\s*expressive emotion,\s*no text\.?$", re.IGNORECASE),
    re.compile(r"^joseon-era dramatic scene,\s*korean faces,\s*expressive emotion,\s*no text\.?$", re.IGNORECASE),
)

ENVIRONMENT_HINT_RE = re.compile(
    r"\b(room|interior|indoors|outdoor|courtyard|market|market lane|lane|road|path|mountain|hut|house|household|residence|noble household|kitchen|prison|gate|village|forest|river|shore|dock|yard|hall|office|court|courtroom|interrogation court|street|lamp|rain|snow|night|dawn|dusk|tent|camp|campyard|barracks|study|library|chamber|inner room)\b",
    re.IGNORECASE,
)


def _load_project(story_id: str) -> Dict[str, Any]:
    path = ROOT / "work" / story_id / "out" / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"missing project.json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_issues(scene: Dict[str, Any], prompt: str) -> List[str]:
    issues: List[str] = []
    ptxt = str(prompt or "").strip()
    if not ptxt:
        return ["empty"]
    if any(p.search(ptxt) for p in GENERIC_PROMPT_PATTERNS):
        issues.append("generic_prompt")
    if re.search(r"[\"“][^\"”\n]{1,260}[\"”]", ptxt):
        issues.append("quoted_dialogue")
    # Treat true speaker-name dialogue as suspicious, but allow structural labels.
    structural_labels = {
        "character",
        "characters",
        "setting",
        "style",
        "mood",
        "lighting",
        "identity",
        "shot",
        "camera",
        "action",
        "visible",
        "primary",
        "subjects",
        "main",
        "negative",
        "continuity",
        "lock",
        "maintain",
        "emotion",
        "wardrobe",
        "props",
    }
    allowed_prefixes = (
        "visible action:",
        "primary subjects:",
        "main character:",
        "setting continuity lock:",
        "camera:",
        "shot:",
        "style:",
        "mood:",
        "negative:",
        "lighting:",
    )
    has_name_colon_dialogue = False
    for m in re.finditer(r"(?:^|\s)([가-힣A-Za-z]{1,16})\s*[:：]\s*[^.\n]{1,180}", ptxt):
        label = str(m.group(1) or "").strip().lower()
        span_txt = str(m.group(0) or "").strip().lower()
        if label in structural_labels:
            continue
        if any(span_txt.startswith(p) for p in allowed_prefixes):
            continue
        # Heuristic: only flag likely speaker labels, not generic lowercase tags.
        if re.fullmatch(r"[a-z]{1,16}", label):
            continue
        has_name_colon_dialogue = True
        break
    if has_name_colon_dialogue:
        issues.append("name_colon_dialogue")
    if re.search(r"\b(?:say|says|said|shout|shouts|shouting|yell|yells|yelling|speech bubble|caption|subtitle)\b", ptxt, re.IGNORECASE):
        issues.append("speech_or_caption_term")
    if re.search(r"\b(?:visible text|letters|words on screen|text overlay|quote marks)\b", ptxt, re.IGNORECASE):
        issues.append("visible_text_term")
    # Flow prompts can be longer due to explicit style/negative constraints.
    if len(ptxt) > 760:
        issues.append("too_long")
    places = scene.get("places")
    if not isinstance(places, list) or not places:
        issues.append("missing_place_tag")
    if not ENVIRONMENT_HINT_RE.search(ptxt):
        issues.append("missing_environment_cue")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story-id", required=True)
    args = ap.parse_args()

    project = _load_project(args.story_id)
    scenes = project.get("scenes", [])
    problems: List[Dict[str, Any]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        sid = int(scene.get("id", 0) or 0)
        prompt = str(scene.get("llm_clip_prompt") or "").strip()
        issues = _find_issues(scene, prompt)
        if issues:
            problems.append({
                "scene_id": sid,
                "chapter_title": str(scene.get("chapter_title") or ""),
                "issues": issues,
                "places": scene.get("places") or [],
                "prompt": prompt,
            })

    if not problems:
        print("OK: no suspicious clip prompts found")
        return 0

    print(f"FOUND {len(problems)} suspicious clip prompts")
    for row in problems:
        print(
            json.dumps(
                {
                    "scene_id": row["scene_id"],
                    "chapter_title": row["chapter_title"],
                    "issues": row["issues"],
                    "places": row["places"],
                    "prompt": row["prompt"],
                },
                ensure_ascii=False,
            )
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
