#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[3]
PROP_RULE_PATH = ROOT / "skills" / "make_vrew" / "references" / "prop_prompt_rules.json"

TRANSITION_RE = re.compile(r"(그때|잠시 후|이윽고|한편|다음|밖으로|들어가|향해|later|after|meanwhile)", re.IGNORECASE)
TEAR_TEXT_RE = re.compile(r"(찢|찢어|찢긴|ripped|torn|tear)", re.IGNORECASE)
PLACE_CUE_RE = re.compile(r"(군막|진영|마당|안채|사랑방|뒷방|산길|길|강변|대문|저택|camp|tent|courtyard|road|river|gate|room)", re.IGNORECASE)
EMOTION_TEXT_RE = re.compile(
    r"(분노|격노|노려보|울|눈물|오열|절규|공포|겁|두려|불안|초조|당황|긴장|다급|안도|한숨|흔들리|떨|비명|절망|체념|흐느끼|scream|panic|fear|afraid|rage|furious|grief|tearful|relief|shocked)",
    re.IGNORECASE,
)
PROMPT_ACTING_CUE_RE = re.compile(
    r"(facial|expression|eyes|gaze|jaw|brow|eyebrow|frown|grimace|tears|tear-streaked|clenched|breathing|panting|posture|gesture|recoil|flinch|stagger|hesitat|protective stance|urgent movement|leans in|turns abruptly|shaking hands)",
    re.IGNORECASE,
)


def _load_project(story_id: str) -> Tuple[Path, Dict[str, Any]]:
    path = ROOT / "work" / story_id / "out" / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"missing project.json: {path}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _load_prop_rules() -> List[Dict[str, Any]]:
    if not PROP_RULE_PATH.exists():
        return []
    raw = json.loads(PROP_RULE_PATH.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for row in raw.get("rules", []) or []:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("mode") or "cue").strip().lower()
        text_pattern = str(row.get("text_pattern") or "").strip()
        text_patterns_any = [str(x).strip() for x in (row.get("text_patterns_any") or []) if str(x).strip()]
        text_patterns_all = [str(x).strip() for x in (row.get("text_patterns_all") or []) if str(x).strip()]
        base: Dict[str, Any] = {
            "rule_id": str(row.get("rule_id") or "").strip(),
            "mode": mode,
            "text_re": re.compile(text_pattern, re.IGNORECASE) if text_pattern else None,
            "text_any_res": [re.compile(p, re.IGNORECASE) for p in text_patterns_any],
            "text_all_res": [re.compile(p, re.IGNORECASE) for p in text_patterns_all],
        }

        if mode == "replace":
            replace_pattern = str(row.get("prompt_replace_pattern") or "").strip()
            if not replace_pattern:
                continue
            base.update(
                {
                    "prompt_replace_re": re.compile(replace_pattern, re.IGNORECASE),
                    "prompt_replace_with": str(row.get("prompt_replace_with") or "").strip(),
                    "repair_fix_id": str(row.get("repair_fix_id") or base["rule_id"] or "replace_prompt_term"),
                }
            )
            out.append(base)
            continue

        prompt_prop_pattern = str(row.get("prompt_prop_pattern") or "").strip()
        if not prompt_prop_pattern:
            continue
        base.update(
            {
                "prompt_prop_re": re.compile(prompt_prop_pattern, re.IGNORECASE),
                "required_res": [re.compile(p, re.IGNORECASE) for p in (row.get("required_prompt_patterns") or []) if isinstance(p, str) and p.strip()],
                "forbidden_re": re.compile(str(row.get("forbidden_prompt_pattern") or ""), re.IGNORECASE)
                if str(row.get("forbidden_prompt_pattern") or "").strip()
                else None,
                "append_missing_prop": str(row.get("repair_append_when_missing_prop") or "").strip(),
                "append_missing_details": str(row.get("repair_append_when_missing_details") or "").strip(),
                "replace_forbidden_with": str(row.get("repair_replace_forbidden_with") or "").strip(),
            }
        )
        out.append(base)
    return out


def _rule_matches_text(text: str, rule: Dict[str, Any]) -> bool:
    text_re = rule.get("text_re")
    text_any_res = rule.get("text_any_res") or []
    text_all_res = rule.get("text_all_res") or []
    matched = False
    if text_re and text_re.search(text):
        matched = True
    if text_any_res and any(r.search(text) for r in text_any_res):
        matched = True
    if text_all_res and all(r.search(text) for r in text_all_res):
        matched = True
    if not text_re and not text_any_res and not text_all_res:
        return True
    return matched


def _variant_map(scene: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    rows = scene.get("character_instances")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("char_id") or "").strip()
        if not cid:
            continue
        out[cid] = str(row.get("variant") or "").strip()
    return out


def _char_set(scene: Dict[str, Any]) -> Set[str]:
    return set(_variant_map(scene).keys())


def _single_place(scene: Dict[str, Any]) -> Optional[str]:
    places = scene.get("places")
    if not isinstance(places, list) or len(places) != 1:
        return None
    p = str(places[0] or "").strip()
    return p or None


def _append_sentence(prompt: str, extra: str) -> str:
    p = (prompt or "").strip()
    if not p:
        return extra.strip()
    if p.endswith("."):
        return p + " " + extra.strip()
    return p + ". " + extra.strip()


def _emotion_acting_cue_sentence(text: str) -> str:
    t = text or ""
    if re.search(r"(분노|격노|rage|furious)", t, re.IGNORECASE):
        return "Facial tension, narrowed eyes, and a clenched jaw show visible anger in motion."
    if re.search(r"(공포|겁|두려|panic|fear|afraid)", t, re.IGNORECASE):
        return "Wide anxious eyes, guarded posture, and a slight recoil show visible fear."
    if re.search(r"(울|눈물|오열|절규|grief|tearful)", t, re.IGNORECASE):
        return "Tear-streaked eyes, trembling breath, and strained posture show visible grief."
    if re.search(r"(안도|한숨|relief)", t, re.IGNORECASE):
        return "A controlled exhale, softened eyes, and shoulders lowering show visible relief."
    return "Readable facial expression and active body gesture show the scene's emotional tension."


def _repair_scene_prompt(scene: Dict[str, Any], prop_rules: List[Dict[str, Any]]) -> List[str]:
    fixes: List[str] = []
    text = str(scene.get("text") or "")
    prompt = str(scene.get("llm_clip_prompt") or "").strip()
    if not prompt:
        return fixes

    # Data-driven replacement rules (style/wording repairs).
    for rule in prop_rules:
        if rule.get("mode") != "replace":
            continue
        if not _rule_matches_text(text, rule):
            continue
        replace_re = rule["prompt_replace_re"]
        replace_with = rule["prompt_replace_with"]
        if not replace_re.search(prompt):
            continue
        prompt = replace_re.sub(replace_with, prompt)
        fixes.append(str(rule.get("repair_fix_id") or rule.get("rule_id") or "replace_prompt_term"))

    vmap = _variant_map(scene)
    y_variant = vmap.get("char_001", "")
    low = prompt.lower()

    if y_variant == "pink_silk_dress" and not any(k in low for k in ("pink", "silk", "disguise")):
        prompt = _append_sentence(prompt, "Her pink silk disguise is clearly visible in motion.")
        fixes.append("add_pink_silk_variant_cue")
        low = prompt.lower()

    if y_variant == "torn_pink_silk" and not any(k in low for k in ("torn", "ripped", "frayed", "pink silk")):
        prompt = _append_sentence(prompt, "Her torn pink silk sleeves and frayed hem are clearly visible.")
        fixes.append("add_torn_silk_variant_cue")
        low = prompt.lower()

    # If script explicitly says tearing but prompt omits tearing cue.
    if y_variant == "torn_pink_silk" and TEAR_TEXT_RE.search(text) and not any(k in low for k in ("torn", "ripped", "tear", "frayed")):
        prompt = _append_sentence(prompt, "Fabric tearing motion is visible in the frame.")
        fixes.append("add_tearing_action_cue")

    if EMOTION_TEXT_RE.search(text) and not PROMPT_ACTING_CUE_RE.search(prompt):
        prompt = _append_sentence(prompt, _emotion_acting_cue_sentence(text))
        fixes.append("add_expression_acting_cue")

    # Data-driven cue rules (palanquin/blade/seal/flame/sickle/jipsin and future extensions).
    for rule in prop_rules:
        if rule.get("mode") != "cue":
            continue
        prompt_prop_re = rule["prompt_prop_re"]
        required_res = rule["required_res"]
        forbidden_re = rule["forbidden_re"]
        append_missing_prop = rule["append_missing_prop"]
        append_missing_details = rule["append_missing_details"]
        replace_forbidden_with = rule["replace_forbidden_with"]
        rid = str(rule.get("rule_id") or "prop_rule")

        if not _rule_matches_text(text, rule):
            continue

        has_prop = bool(prompt_prop_re.search(prompt))
        if not has_prop and append_missing_prop:
            prompt = _append_sentence(prompt, append_missing_prop)
            fixes.append(f"{rid}_add_prop_cue")
            has_prop = True

        if has_prop:
            missing_detail = any(not need_re.search(prompt) for need_re in required_res)
            if missing_detail and append_missing_details:
                prompt = _append_sentence(prompt, append_missing_details)
                fixes.append(f"{rid}_add_detail_cue")

        if forbidden_re and forbidden_re.search(prompt):
            if replace_forbidden_with:
                prompt = forbidden_re.sub(replace_forbidden_with, prompt)
            fixes.append(f"{rid}_remove_forbidden_wording")

    if prompt != str(scene.get("llm_clip_prompt") or ""):
        scene["llm_clip_prompt"] = prompt
    return fixes


def _repair_adjacent_context(prev: Dict[str, Any], cur: Dict[str, Any], nxt: Dict[str, Any]) -> List[str]:
    fixes: List[str] = []
    cur_text = str(cur.get("text") or "")
    chapter_prev = int(prev.get("chapter_no", 0) or 0)
    chapter_cur = int(cur.get("chapter_no", 0) or 0)
    chapter_next = int(nxt.get("chapter_no", 0) or 0)

    prev_place = _single_place(prev)
    cur_place = _single_place(cur)
    next_place = _single_place(nxt)
    # If prev/next agree on a place and current is different with no transition cue, align current.
    if (
        prev_place
        and next_place
        and prev_place == next_place
        and cur_place
        and cur_place != prev_place
        and not TRANSITION_RE.search(cur_text)
        and chapter_prev == chapter_cur == chapter_next
        and len(cur_text.strip()) <= 90
        and not PLACE_CUE_RE.search(cur_text)
    ):
        cur["places"] = [prev_place]
        fixes.append("align_place_with_prev_next")

    prev_chars = _char_set(prev)
    cur_chars = _char_set(cur)
    next_chars = _char_set(nxt)

    # If Yeonhwa appears in both neighbor scenes but disappears in current scene while text mentions her, reinsert.
    if "char_001" in prev_chars and "char_001" in next_chars and "char_001" not in cur_chars and ("연화" in cur_text):
        prev_v = _variant_map(prev).get("char_001", "")
        next_v = _variant_map(nxt).get("char_001", "")
        chosen_v = prev_v or next_v
        rows = cur.get("character_instances")
        if not isinstance(rows, list):
            rows = []
        rows.append({"char_id": "char_001", "variant": chosen_v})
        cur["character_instances"] = rows
        fixes.append("reinsert_yeonhwa_from_neighbors")

    return fixes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Auto-repair adjacent clip context continuity (background, cast, props) before step 9."
    )
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--apply", action="store_true", help="Write fixes to project.json. Without this flag, run in dry-run mode.")
    args = ap.parse_args()

    path, project = _load_project(args.story_id)
    prop_rules = _load_prop_rules()
    scenes = [s for s in project.get("scenes", []) if isinstance(s, dict)]
    if not scenes:
        raise RuntimeError("project.json has no scenes")

    modified: Dict[int, List[str]] = {}

    for i, scene in enumerate(scenes):
        sid = int(scene.get("id", 0) or 0)
        f1 = _repair_scene_prompt(scene, prop_rules)
        if f1:
            modified.setdefault(sid, []).extend(f1)

        if 0 < i < len(scenes) - 1:
            f2 = _repair_adjacent_context(scenes[i - 1], scene, scenes[i + 1])
            if f2:
                modified.setdefault(sid, []).extend(f2)

    if not modified:
        print("OK: no context continuity fixes needed")
        return 0

    if args.apply:
        project["scenes"] = scenes
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"APPLIED {len(modified)} scene fixes")
    else:
        print(f"FOUND {len(modified)} scene fix candidates (dry-run)")

    for sid in sorted(modified.keys()):
        print(
            json.dumps(
                {
                    "scene_id": sid,
                    "fixes": sorted(set(modified[sid])),
                },
                ensure_ascii=False,
            )
        )

    return 0 if args.apply else 1


if __name__ == "__main__":
    sys.exit(main())
