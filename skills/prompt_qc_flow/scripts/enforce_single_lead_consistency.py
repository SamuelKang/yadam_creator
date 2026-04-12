#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STYLE_BLOCK = (
    "Ghibli-inspired hand-drawn 2D animation, painterly illustrated look, "
    "non-photorealistic rendering"
)

CHAR_BLOCK = (
    "Main character: Korean male, early 40s, lean face, sharp cheekbones, "
    "narrow tired eyes, slightly tanned skin, thin mustache and short beard, "
    "traditional Joseon-era topknot (sangtu), worn brown hanbok with patched sleeves "
    "and rope belt, serious and restrained expression"
)

NEG_BLOCK = (
    "no modern hairstyle, no k-pop style, no japanese anime style, no text, "
    "no watermark, no extra characters, no different face"
)

PROPER_NOUN_RE = re.compile(
    r"\b(Shim|Yeonhwa|Choi Jinsa|Park Seobang|Joseon|청석골|연화|심 씨|최 진사|박 서방)\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _scene_block(scene: dict, idx: int) -> str:
    src = _norm(scene.get("llm_clip_prompt") or "")
    text = _norm(scene.get("text") or "")

    camera = "medium shot"
    m = re.search(r"\b(close-up|medium shot|two-shot|wide shot|medium-wide shot)\b", src, re.IGNORECASE)
    if m:
        camera = m.group(1).lower()
    if idx % 4 == 0:
        camera = "close-up shot of the character's face"

    action = ""
    am = re.search(r"Visible action:\s*(.+?)(?:\.\s*Mood:|$)", src, re.IGNORECASE)
    if am:
        action = _norm(am.group(1))
    if not action:
        action = text or "the character moves with restrained urgency"

    action = PROPER_NOUN_RE.sub("the character", action)
    action = re.sub(r"\b(crowd|villagers|laborers|many people|group)\b", "background presence", action, flags=re.IGNORECASE)

    return (
        f"{camera}. same character, consistent appearance. "
        f"{action}. emotion-focused acting, coherent anatomy."
    )


def _rewrite(scene: dict, idx: int) -> str:
    return "\n".join([STYLE_BLOCK, CHAR_BLOCK, _scene_block(scene, idx), NEG_BLOCK]).strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Single-lead character consistency enforcement for Flow prompts."
    )
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    pj = Path(f"work/{args.story_id}/out/project.json")
    if not pj.exists():
        raise SystemExit(f"missing: {pj}")
    data = json.loads(pj.read_text(encoding="utf-8"))

    changed = 0
    previews = []
    for idx, s in enumerate(data.get("scenes", []), start=1):
        new_prompt = _rewrite(s, idx)
        old_prompt = s.get("llm_clip_prompt") or ""
        if _norm(old_prompt) != _norm(new_prompt):
            changed += 1
            previews.append({"scene_id": s.get("id"), "preview": new_prompt[:220]})
            if args.apply:
                s["llm_clip_prompt"] = new_prompt
                if isinstance(s.get("image"), dict):
                    s["image"]["prompt_used"] = new_prompt

    if args.apply and changed:
        pj.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = Path(f"work/{args.story_id}/out/single_lead_consistency_report.json")
    out.write_text(
        json.dumps(
            {
                "story_id": args.story_id,
                "mode": "apply" if args.apply else "check",
                "style_block": STYLE_BLOCK,
                "character_block": CHAR_BLOCK,
                "negative_block": NEG_BLOCK,
                "changed_scenes": changed,
                "samples": previews[:12],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "changed_scenes": changed, "report": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

