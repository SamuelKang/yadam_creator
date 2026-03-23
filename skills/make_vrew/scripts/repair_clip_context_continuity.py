#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
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
STOCK_ACTING_SENTENCE_RE = re.compile(
    r"(?:\.\s*)?(Readable facial expression and active body gesture show the scene's emotional tension\.|"
    r"Readable facial expression and active body gesture match the dramatic beat\.|"
    r"Wide anxious eyes, guarded posture, and a slight recoil show visible fear\.|"
    r"Wide fearful eyes, recoiling posture, and protective movement drive the acting\.|"
    r"Tear-streaked eyes, trembling breath, and strained posture show visible grief\.|"
    r"Tearful eyes, trembling breath, and shaking shoulders drive the acting\.|"
    r"A controlled exhale, softened eyes, and shoulders lowering show visible relief\.|"
    r"Facial tension, narrowed eyes, and a clenched jaw show visible anger in motion\.)",
    re.IGNORECASE,
)
BORING_TEMPLATE_RE = re.compile(
    r"(empty establishing shot|Korean historical-drama mood in clean webtoon style|Readable facial expression and active body gesture match the dramatic beat)",
    re.IGNORECASE,
)
SHOT_PREFIX_RE = re.compile(
    r"^(Extreme wide aerial shot|Wide street-level shot|Tight two-shot|Over-shoulder shot|Medium shot|Wide shot|Close-up|Low-angle shot|High-angle shot|Detail insert shot|Two-shot|Reaction-focused medium shot|Dynamic close-medium shot)\s+",
    re.IGNORECASE,
)
GLOBAL_SHOT_PLAN = [
    "Low-angle tracking shot",
    "High-angle tension shot",
    "Over-shoulder reaction shot",
    "Tight two-shot",
    "Dynamic medium shot",
    "Wide movement shot",
    "Close-up reaction shot",
    "Diagonal composition shot",
    "Street-level perspective shot",
    "Foreground-obstacle shot",
]
ROLE_ONLY_TERM_RE = re.compile(
    r"(adopted daughter|true daughter|biological daughter|foster daughter|real daughter|adoptive daughter|"
    r"adopted son|true son|biological son|foster son|real son|adoptive son|양녀|친딸|양자|친아들)",
    re.IGNORECASE,
)
INTRO_SCENE_COUNT = 5
INTRO_SHOT_PLAN = [
    "Extreme wide aerial shot",
    "Medium shot",
    "Tight two-shot",
    "Over-shoulder shot",
    "Wide street-level shot",
]


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


def _drop_stock_acting_sentence(prompt: str) -> str:
    p = str(prompt or "").strip()
    if not p:
        return p
    p2 = STOCK_ACTING_SENTENCE_RE.sub("", p)
    p2 = re.sub(r"\s{2,}", " ", p2).strip()
    if p2.endswith(".."):
        p2 = p2[:-1]
    return p2


def _dynamic_action_sentence(text: str) -> str:
    t = text or ""
    if re.search(r"(속삭|쉿|낮은 목소리|whisper)", t, re.IGNORECASE):
        return "One figure leans in while another reacts immediately, keeping motion readable in-frame."
    if re.search(r"(뒷걸음|물러서|도망|달리|rush|run|retreat)", t, re.IGNORECASE):
        return "Show clear retreat motion and reactive posture change across the frame."
    if re.search(r"(붙잡|막|가로막|막아서|grab|block)", t, re.IGNORECASE):
        return "Capture the instant one character restrains another with visible arm and torso motion."
    if re.search(r"(칼|검|겨누|베|찌르|slash|stab|blade)", t, re.IGNORECASE):
        return "Keep blade direction and defensive recoil readable with dynamic body angles."
    if re.search(r"(울|눈물|오열|절규|tear|cry|sob)", t, re.IGNORECASE):
        return "Tearful eyes and shaking breath should be paired with active body movement."
    if re.search(r"(의심|경계|불안|초조|당황|긴장|suspicious|anxious|tense)", t, re.IGNORECASE):
        return "Use shifting gaze and guarded stance so tension is shown through movement, not a static pose."
    return "Use active movement and reaction timing so the scene does not read as a static pose."


def _replace_empty_establishing(prompt: str, has_people: bool) -> str:
    if "empty establishing shot" not in prompt.lower():
        return prompt
    if not has_people:
        return prompt
    out = re.sub(
        r"empty establishing shot with no people or animals in frame\.?\s*",
        "active dramatic staging with people in motion and readable reactions. ",
        prompt,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"No incident staging, no silhouettes, no crowd close-up; focus on environmental mood and spatial clarity\.?\s*",
        "Keep spatial clarity while showing active character interaction and foreground-background depth. ",
        out,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s{2,}", " ", out).strip()


def _boost_cut_intensity(scene: Dict[str, Any]) -> List[str]:
    prompt = str(scene.get("llm_clip_prompt") or "").strip()
    if not prompt:
        return []
    if not BORING_TEMPLATE_RE.search(prompt):
        return []

    fixes: List[str] = []
    sid = int(scene.get("id", 0) or 0)
    shot = GLOBAL_SHOT_PLAN[(max(1, sid) - 1) % len(GLOBAL_SHOT_PLAN)]
    if SHOT_PREFIX_RE.search(prompt):
        replaced = SHOT_PREFIX_RE.sub(f"{shot} ", prompt)
        if replaced != prompt:
            prompt = replaced
            fixes.append("raise_cut_intensity_shot_variation")
    else:
        prompt = f"{shot} {prompt}"
        fixes.append("raise_cut_intensity_shot_variation")

    has_people = bool(scene.get("characters")) or bool(scene.get("character_instances"))
    rep = _replace_empty_establishing(prompt, has_people)
    if rep != prompt:
        prompt = rep
        fixes.append("replace_empty_establishing_with_dynamic_staging")

    if "Korean historical-drama mood in clean webtoon style" in prompt:
        prompt = prompt.replace("Korean historical-drama mood in clean webtoon style", "Korean webtoon style")
        fixes.append("normalize_style_suffix")

    cleaned = _drop_stock_acting_sentence(prompt)
    if cleaned != prompt:
        prompt = cleaned
        fixes.append("remove_stock_acting_sentence")

    action = _dynamic_action_sentence(str(scene.get("text") or ""))
    if action.lower() not in prompt.lower():
        prompt = _append_sentence(prompt, action)
        fixes.append("add_dynamic_action_direction")

    scene["llm_clip_prompt"] = prompt
    return fixes


def _first_n_scenes_by_id(scenes: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    ordered = sorted(
        [s for s in scenes if int(s.get("id", 0) or 0) > 0],
        key=lambda s: int(s.get("id", 0) or 0),
    )
    return ordered[:n]


def _normalize_intro_prompt(prompt: str) -> str:
    low = str(prompt or "").strip().lower()
    if not low:
        return ""
    low = re.sub(
        r"^(extreme wide aerial shot|wide street-level shot|tight two-shot|over-shoulder shot|medium shot|wide shot|close-up|two-shot)\s+",
        "",
        low,
    )
    low = re.sub(r"\s+", " ", low)
    return low.strip(" ,.")


def _intro_repetition_risk(intro_scenes: List[Dict[str, Any]]) -> bool:
    prompts = [str(s.get("llm_clip_prompt") or "").strip() for s in intro_scenes]
    if len(prompts) < INTRO_SCENE_COUNT:
        return False
    lows = [p.lower() for p in prompts]
    empty_count = sum("empty establishing shot" in p for p in lows)
    if empty_count >= 2:
        return True
    norms = [_normalize_intro_prompt(p) for p in prompts if p.strip()]
    if not norms:
        return False
    common = Counter(norms).most_common(1)[0][1]
    return common >= 3


def _intro_prompt_from_scene(scene: Dict[str, Any], idx: int) -> str:
    text = str(scene.get("text") or "")
    low_text = text.lower()
    shot = INTRO_SHOT_PLAN[min(max(idx, 0), len(INTRO_SHOT_PLAN) - 1)]

    if idx == 0:
        action = (
            "over drought-stricken land outside the Joseon capital, cracked fields and heat haze stretching far into the distance"
        )
        people = "no people in frame"
    elif "우물" in text or "well" in low_text:
        action = (
            "at a dry village well, one villager lowers an empty bucket while another watches with anxious eyes"
        )
        people = "two people only"
    elif ("속삭" in text) or ("whisper" in low_text):
        action = (
            "beside the dry well, one villager whispers while another quickly hushes them, both scanning nearby listeners"
        )
        people = "two people only"
    elif ("쉿" in text) or ("소문" in text) or ("warn" in low_text):
        action = (
            "in a dusty market lane, a speaker leans in to warn quietly while background bystanders pause and glance over"
        )
        people = "foreground two people with sparse background figures"
    elif ("노을" in text) or ("의심" in text) or ("shadow" in low_text):
        action = (
            "at red dusk in the Joseon capital, villagers trade suspicious glances as dust blows and long shadows cut across the road"
        )
        people = "small crowd with clear spacing"
    else:
        action = (
            "in a drought-stricken Joseon street, villagers react with uneasy glances and restless movement as dust drifts through frame"
        )
        people = "visible people with active body language"

    return (
        f"{shot} {action}, {people}. "
        "Korean webtoon style, full-frame 16:9, no text, no speech bubbles, no captions, no logos."
    )


def _repair_intro_shot_diversity(scenes: List[Dict[str, Any]]) -> Dict[int, List[str]]:
    intro = _first_n_scenes_by_id(scenes, INTRO_SCENE_COUNT)
    if not _intro_repetition_risk(intro):
        return {}

    modified: Dict[int, List[str]] = {}
    for idx, scene in enumerate(intro):
        sid = int(scene.get("id", 0) or 0)
        new_prompt = _intro_prompt_from_scene(scene, idx)
        if str(scene.get("llm_clip_prompt") or "").strip() == new_prompt:
            continue
        scene["llm_clip_prompt"] = new_prompt
        modified.setdefault(sid, []).append("intro_shot_diversity_rewrite")
    return modified


def _scene_identity_lock(scene: Dict[str, Any], char_map: Dict[str, Dict[str, Any]]) -> str:
    prompt = str(scene.get("llm_clip_prompt") or "").strip()
    if not prompt or not ROLE_ONLY_TERM_RE.search(prompt):
        return prompt
    if re.search(r"\bcharacter\s*a\b", prompt, re.IGNORECASE) and re.search(r"\bcharacter\s*b\b", prompt, re.IGNORECASE):
        return prompt

    cids = [str(x) for x in (scene.get("characters") or []) if str(x).strip()]
    if len(cids) < 2:
        return prompt

    lines: List[str] = []
    for idx, cid in enumerate(cids[:2]):
        cobj = char_map.get(cid, {})
        visual = [str(x).strip() for x in (cobj.get("visual_anchors") or []) if str(x).strip()]
        wardrobe = [str(x).strip() for x in (cobj.get("wardrobe_anchors") or []) if str(x).strip()]
        g = str(cobj.get("gender") or "")
        role = "woman" if g == "여" else ("man" if g == "남" else "person")
        visual_txt = ", ".join(visual[:2]) if visual else "keep distinct face and body type"
        wardrobe_txt = ", ".join(wardrobe[:2]) if wardrobe else "keep distinct outfit silhouette"
        tag = "A" if idx == 0 else "B"
        lines.append(f"Character {tag}: Korean {role} in Joseon-era hanbok; visual anchors={visual_txt}; wardrobe anchors={wardrobe_txt}.")

    if len(lines) < 2:
        return prompt

    lock = (
        "Identity lock: Keep exactly one Character A and exactly one Character B in frame. "
        "Never swap Character A/B face, body type, or outfit."
    )
    return f"{prompt} {lock} " + " ".join(lines)


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


def _repair_scene_prompt(scene: Dict[str, Any], prop_rules: List[Dict[str, Any]], char_map: Dict[str, Dict[str, Any]]) -> List[str]:
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

    is_empty_establishing = "empty establishing shot" in low
    has_people = bool(scene.get("characters")) or bool(scene.get("character_instances"))
    if is_empty_establishing and PROMPT_ACTING_CUE_RE.search(prompt):
        cleaned = _drop_stock_acting_sentence(prompt)
        if cleaned != prompt:
            prompt = cleaned
            fixes.append("remove_acting_cue_from_empty_establishing")
            low = prompt.lower()
    if EMOTION_TEXT_RE.search(text) and not PROMPT_ACTING_CUE_RE.search(prompt) and not is_empty_establishing and has_people:
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

    locked = _scene_identity_lock({**scene, "llm_clip_prompt": prompt}, char_map)
    if locked != prompt:
        prompt = locked
        fixes.append("add_role_identity_lock_ab")

    if prompt != str(scene.get("llm_clip_prompt") or ""):
        scene["llm_clip_prompt"] = prompt
    return fixes


def _infer_place_from_text(text: str, prompt: str, place_name_to_id: Dict[str, str]) -> Optional[str]:
    combined = f"{text} {prompt}".lower()

    def _id_for(k: str) -> Optional[str]:
        return place_name_to_id.get(k)

    if any(x in combined for x in ("시장", "저잣거리", "market", "bazaar")):
        return _id_for("시장")
    if any(x in combined for x in ("관아", "의금부", "interrogation court", "magistrate office")):
        return _id_for("관아")
    if any(x in combined for x in ("마당", "뒤뜰", "뜰", "courtyard")):
        return _id_for("마당")
    if any(x in combined for x in ("방", "서재", "사랑채", "내실", "inner room", "study", "chamber")):
        return _id_for("방")
    if any(x in combined for x in ("저택", "대감댁", "집", "household", "residence", "house")):
        return _id_for("집")
    if any(x in combined for x in ("산", "mountain", "hillside")):
        return _id_for("산")
    if any(x in combined for x in ("절", "temple")):
        return _id_for("절")
    return None


def _repair_adjacent_context(
    prev: Dict[str, Any],
    cur: Dict[str, Any],
    nxt: Dict[str, Any],
    place_name_to_id: Dict[str, str],
) -> List[str]:
    fixes: List[str] = []
    cur_text = str(cur.get("text") or "")
    cur_prompt = str(cur.get("llm_clip_prompt") or "")
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
    # If current place is missing and neighbors agree, inherit that place.
    if (
        prev_place
        and next_place
        and prev_place == next_place
        and not cur_place
        and not TRANSITION_RE.search(cur_text)
        and chapter_prev == chapter_cur == chapter_next
    ):
        cur["places"] = [prev_place]
        fixes.append("fill_missing_place_from_neighbors")
    # If current place is missing, inherit from previous scene in the same chapter
    # unless the script text explicitly signals a transition.
    if (
        not _single_place(cur)
        and prev_place
        and chapter_prev == chapter_cur
        and not TRANSITION_RE.search(cur_text)
    ):
        cur["places"] = [prev_place]
        fixes.append("fill_missing_place_from_previous")
    # If current place is missing, inherit from next scene in same chapter
    # when no explicit transition appears in current text.
    if (
        not _single_place(cur)
        and next_place
        and chapter_next == chapter_cur
        and not TRANSITION_RE.search(cur_text)
    ):
        cur["places"] = [next_place]
        fixes.append("fill_missing_place_from_next")
    # Text/prompt semantic inference fallback for still-missing places.
    if not _single_place(cur):
        inferred = _infer_place_from_text(cur_text, cur_prompt, place_name_to_id)
        if inferred:
            cur["places"] = [inferred]
            fixes.append("infer_place_from_text_prompt")

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
    char_map: Dict[str, Dict[str, Any]] = {
        str(c.get("id")): c
        for c in (project.get("characters") or [])
        if isinstance(c, dict) and str(c.get("id") or "").strip()
    }
    scenes = [s for s in project.get("scenes", []) if isinstance(s, dict)]
    place_name_to_id: Dict[str, str] = {}
    for p in (project.get("places") or []):
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        name = str(p.get("name") or "").strip()
        if pid and name:
            place_name_to_id[name] = pid
    if not scenes:
        raise RuntimeError("project.json has no scenes")

    modified: Dict[int, List[str]] = {}

    for i, scene in enumerate(scenes):
        sid = int(scene.get("id", 0) or 0)
        f1 = _repair_scene_prompt(scene, prop_rules, char_map)
        if f1:
            modified.setdefault(sid, []).extend(f1)

        f1b = _boost_cut_intensity(scene)
        if f1b:
            modified.setdefault(sid, []).extend(f1b)

        if 0 < i < len(scenes) - 1:
            f2 = _repair_adjacent_context(scenes[i - 1], scene, scenes[i + 1], place_name_to_id)
            if f2:
                modified.setdefault(sid, []).extend(f2)

    intro_fixes = _repair_intro_shot_diversity(scenes)
    for sid, fixes in intro_fixes.items():
        modified.setdefault(sid, []).extend(fixes)

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
