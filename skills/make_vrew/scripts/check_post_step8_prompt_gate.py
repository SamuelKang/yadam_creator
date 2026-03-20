#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


ROOT = Path(__file__).resolve().parents[3]
PROP_RULE_PATH = ROOT / "skills" / "make_vrew" / "references" / "prop_prompt_rules.json"

STATIC_PROMPT_RE = re.compile(
    r"\b(tense stillness|stillness|static portrait|front-facing|standing still|calm stillness)\b",
    re.IGNORECASE,
)

DYNAMIC_TEXT_RE = re.compile(
    r"(울부짖|비명|달리|도망|붙잡|끌려|내던지|찢|불태|칼|겨누|밀어|가로막|휘둘|오열|절규|몸부림|무릎|run|rush|drag|tear|rip|slash|stab|scream|yell)",
    re.IGNORECASE,
)

RIVER_TEXT_RE = re.compile(r"(강|강변|압록강|강가|물가|river|shore|frozen)", re.IGNORECASE)
EMOTION_TEXT_RE = re.compile(
    r"(분노|격노|노려보|울|눈물|오열|절규|공포|겁|두려|불안|초조|당황|긴장|다급|안도|한숨|흔들리|떨|비명|절망|체념|흐느끼|scream|panic|fear|afraid|rage|furious|grief|tearful|relief|shocked)",
    re.IGNORECASE,
)
PROMPT_ACTING_CUE_RE = re.compile(
    r"(facial|expression|eyes|gaze|jaw|brow|eyebrow|frown|grimace|tears|tear-streaked|clenched|breathing|panting|posture|gesture|recoil|flinch|stagger|hesitat|protective stance|urgent movement|leans in|turns abruptly|shaking hands)",
    re.IGNORECASE,
)


def _load_project(story_id: str) -> Dict[str, Any]:
    path = ROOT / "work" / story_id / "out" / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"missing project.json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_prop_rules() -> List[Dict[str, Any]]:
    if not PROP_RULE_PATH.exists():
        return []
    raw = json.loads(PROP_RULE_PATH.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for row in raw.get("rules", []) or []:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("mode") or "cue").strip().lower()
        if mode != "cue":
            continue
        text_pattern = str(row.get("text_pattern") or "").strip()
        text_patterns_any = [str(x).strip() for x in (row.get("text_patterns_any") or []) if str(x).strip()]
        text_patterns_all = [str(x).strip() for x in (row.get("text_patterns_all") or []) if str(x).strip()]
        prompt_prop_pattern = str(row.get("prompt_prop_pattern") or "").strip()
        if not (text_pattern or text_patterns_any or text_patterns_all):
            continue
        if not prompt_prop_pattern:
            continue
        out.append(
            {
                "rule_id": str(row.get("rule_id") or "").strip(),
                "text_re": re.compile(text_pattern, re.IGNORECASE) if text_pattern else None,
                "text_any_res": [re.compile(p, re.IGNORECASE) for p in text_patterns_any],
                "text_all_res": [re.compile(p, re.IGNORECASE) for p in text_patterns_all],
                "prompt_prop_re": re.compile(prompt_prop_pattern, re.IGNORECASE),
                "required_res": [re.compile(p, re.IGNORECASE) for p in (row.get("required_prompt_patterns") or []) if isinstance(p, str) and p.strip()],
                "forbidden_re": re.compile(str(row.get("forbidden_prompt_pattern") or ""), re.IGNORECASE)
                if str(row.get("forbidden_prompt_pattern") or "").strip()
                else None,
                "missing_issue_ids": [str(x) for x in (row.get("missing_issue_ids") or []) if str(x).strip()],
                "forbidden_issue_id": str(row.get("forbidden_issue_id") or "").strip(),
            }
        )
    return out


def _collect_proper_nouns(project: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    for c in project.get("characters", []) or []:
        if not isinstance(c, dict):
            continue
        for t in [c.get("name")] + list(c.get("aliases") or []):
            if isinstance(t, str):
                s = t.strip()
                if len(s) >= 2:
                    tokens.add(s)
    for p in project.get("places", []) or []:
        if not isinstance(p, dict):
            continue
        t = p.get("name")
        if isinstance(t, str):
            s = t.strip()
            if len(s) >= 2:
                tokens.add(s)
    # Common romanized spellings seen in this project family.
    tokens.update(
        {
            "Yeon-hwa",
            "Yeonhwa",
            "Seo-yun",
            "Seoyun",
            "Myeong-jin",
            "Myeongjin",
            "Arabu",
            "Pan-seo",
            "Yi Pan-seo",
        }
    )
    return tokens


def _contains_token(prompt: str, token: str) -> bool:
    if not token:
        return False
    # Use case-insensitive word-boundary matching for ASCII-like tokens.
    if re.fullmatch(r"[A-Za-z0-9 _\-']+", token):
        if re.search(rf"\b{re.escape(token)}\b", prompt, flags=re.IGNORECASE):
            return True
        # Also catch compact variants like "Yeonhwa" vs "Yeon-hwa"/"Yeon hwa".
        compact_token = re.sub(r"[\s_\-']", "", token).lower()
        compact_prompt = re.sub(r"[\s_\-']", "", prompt).lower()
        if compact_token and compact_token in compact_prompt:
            return True
        return False
    return token in prompt


def _variant_set(scene: Dict[str, Any], char_id: str) -> Set[str]:
    out: Set[str] = set()
    rows = scene.get("character_instances")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("char_id") or "") != char_id:
            continue
        v = str(row.get("variant") or "").strip()
        if v:
            out.add(v)
    return out


def _issues_for_scene(scene: Dict[str, Any], proper_nouns: Set[str], prop_rules: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    prompt = str(scene.get("llm_clip_prompt") or "").strip()
    if not prompt:
        return ["empty_prompt"]

    # 1) Proper nouns in clip prompts.
    found = [t for t in proper_nouns if _contains_token(prompt, t)]
    if found:
        issues.append("proper_noun_in_prompt")

    # 2) Static/stiff prompt language.
    if STATIC_PROMPT_RE.search(prompt):
        issues.append("stiff_standing_risk")

    # 3) Dynamic script vs static prompt conflict.
    text = str(scene.get("text") or "")
    if DYNAMIC_TEXT_RE.search(text) and STATIC_PROMPT_RE.search(prompt):
        issues.append("dynamic_text_but_static_prompt")

    # 3-1) Script emotion/acting beat should have facial/body acting cue in prompt.
    if EMOTION_TEXT_RE.search(text) and not PROMPT_ACTING_CUE_RE.search(prompt):
        issues.append("expression_acting_cue_missing")

    # 4) Known high-impact mismatch pattern.
    if "frozen river shore" in prompt.lower() and not RIVER_TEXT_RE.search(text):
        issues.append("frozen_river_mismatch")

    # 5) Variant cue must be visible in prompt when Yeonhwa variants are active.
    y_variants = _variant_set(scene, "char_001")
    low = prompt.lower()
    if "pink_silk_dress" in y_variants and not any(k in low for k in ("pink", "silk", "disguise")):
        issues.append("variant_cue_missing_pink_silk")
    if "torn_pink_silk" in y_variants and not any(k in low for k in ("torn", "ripped", "frayed", "pink silk")):
        issues.append("variant_cue_missing_torn_silk")

    # 6) Joseon prop-shape continuity checks from data table.
    for rule in prop_rules:
        text_re = rule["text_re"]
        text_any_res = rule["text_any_res"]
        text_all_res = rule["text_all_res"]
        prompt_prop_re = rule["prompt_prop_re"]
        required_res = rule["required_res"]
        forbidden_re = rule["forbidden_re"]
        missing_issue_ids = rule["missing_issue_ids"]
        forbidden_issue_id = rule["forbidden_issue_id"]

        matched_text = False
        if text_re and text_re.search(text):
            matched_text = True
        if text_any_res and any(r.search(text) for r in text_any_res):
            matched_text = True
        if text_all_res and all(r.search(text) for r in text_all_res):
            matched_text = True
        if not matched_text:
            continue

        if not prompt_prop_re.search(prompt):
            if missing_issue_ids:
                issues.append(missing_issue_ids[0])
        else:
            for idx, need_re in enumerate(required_res):
                if need_re.search(prompt):
                    continue
                if idx < len(missing_issue_ids):
                    issues.append(missing_issue_ids[idx])
                elif missing_issue_ids:
                    issues.append(missing_issue_ids[-1])

        if forbidden_re and forbidden_issue_id and forbidden_re.search(prompt):
            issues.append(forbidden_issue_id)

    return issues


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Post-step8 mandatory clip-prompt gate: proper nouns, mismatch, stiff pose, and Joseon prop/state risks."
    )
    ap.add_argument("--story-id", required=True)
    args = ap.parse_args()

    project = _load_project(args.story_id)
    proper_nouns = _collect_proper_nouns(project)
    prop_rules = _load_prop_rules()

    problems: List[Dict[str, Any]] = []
    for scene in project.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue
        sid = int(scene.get("id", 0) or 0)
        issues = _issues_for_scene(scene, proper_nouns, prop_rules)
        if not issues:
            continue
        problems.append(
            {
                "scene_id": sid,
                "chapter_title": str(scene.get("chapter_title") or ""),
                "issues": issues,
                "prompt": str(scene.get("llm_clip_prompt") or ""),
            }
        )

    if not problems:
        print("OK: post-step8 prompt gate passed")
        return 0

    print(f"FOUND {len(problems)} post-step8 prompt gate issues")
    for row in problems:
        print(json.dumps(row, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
