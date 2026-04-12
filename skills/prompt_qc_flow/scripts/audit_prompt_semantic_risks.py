#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[3]

PLACE_EXPECTED_CUES: Dict[str, Tuple[str, List[str]]] = {
    "place_001": ("village", ["village", "lane", "street", "hamlet", "market"]),
    "place_002": ("mountain", ["mountain", "ridge", "slope", "forest", "path"]),
    "place_003": ("temple", ["temple", "shrine"]),
    "place_004": ("magistrate office", ["magistrate", "court", "government office"]),
    "place_005": ("house", ["house", "home", "residence", "courtyard"]),
    "place_006": ("room", ["room", "interior", "chamber", "indoors"]),
    "place_007": ("courtyard", ["courtyard", "yard", "madang"]),
    "place_008": ("night intrusion", ["night", "dark", "torch", "shadow", "gate", "infiltrat"]),
    "place_009": ("gate courtyard", ["gate", "courtyard", "yard"]),
}

TEMPLATE_PHRASES = [
    "a single clear beat plays out through body movement and eye-line control",
    "the rusty korean sickle turns in one compact arc and cuts through tough vines",
    "tear-streaked eyes, trembling breath, and strained posture show visible grief",
]

GRIEF_PROMPT_RE = re.compile(
    r"(tear-streaked|visible grief|grief|tearful|sobbing|sob|weeping|wailing|오열|눈물|슬픔|비통|통곡)",
    re.IGNORECASE,
)
GRIEF_TEXT_RE = re.compile(r"(오열|눈물|울음|흐느끼|슬픔|비통|통곡|비탄)", re.IGNORECASE)
TENSE_TEXT_RE = re.compile(
    r"(서늘|경계|긴장|침묵|정체|은닉|대치|잠입|침입|추격|의심|살피|망설|노려|숨죽)",
    re.IGNORECASE,
)
ACTION_TEXT_RE = re.compile(
    r"(붙잡|밀치|때리|휘두르|베|찌르|도망|추격|잠입|침입|제압|run|rush|slash|stab|chase|infiltrat|fight)",
    re.IGNORECASE,
)

GENERIC_ACTION_PROMPT_RE = re.compile(
    r"(single clear beat plays out|body movement and eye-line control|generic two-shot|two-shot medium)",
    re.IGNORECASE,
)
CONTINUITY_LOCK_RE = re.compile(r"setting continuity lock:\s*.*same\s+([a-z\- ]+)\.", re.IGNORECASE)

# Residual carry-over names/places from other stories. Only flag when absent from current project tokens.
CARRYOVER_TOKENS = {
    "shim",
    "hanyang",
    "cheongseokgol",
    "pan-seo",
    "yi pan-seo",
}


@dataclass
class Finding:
    scene_id: int
    issue: str
    severity: str
    detail: str


def _load_project(story_id: str) -> dict:
    p = ROOT / "work" / story_id / "out" / "project.json"
    if not p.exists():
        raise FileNotFoundError(f"missing project.json: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _contains_any(haystack: str, needles: List[str]) -> bool:
    low = (haystack or "").lower()
    return any(n.lower() in low for n in needles)


def _collect_known_tokens(data: dict) -> Set[str]:
    tokens: Set[str] = set()
    for row in data.get("characters", []):
        if not isinstance(row, dict):
            continue
        for t in [row.get("name")] + list(row.get("aliases") or []):
            ts = str(t or "").strip()
            if ts:
                tokens.add(ts.lower())
    for row in data.get("places", []):
        if not isinstance(row, dict):
            continue
        ts = str(row.get("name") or "").strip()
        if ts:
            tokens.add(ts.lower())
    return tokens


def _scene_findings(scene: dict, known_tokens: Set[str], template_counts: Counter[str]) -> List[Finding]:
    out: List[Finding] = []
    sid = int(scene.get("id") or 0)
    text = str(scene.get("text") or "")
    prompt = str(scene.get("llm_clip_prompt") or "")
    prompt_l = prompt.lower()

    for phrase in TEMPLATE_PHRASES:
        if phrase in prompt_l and template_counts[phrase] >= 4:
            out.append(
                Finding(
                    scene_id=sid,
                    issue="template_phrase_overused",
                    severity="medium",
                    detail=f"repeated template phrase appears {template_counts[phrase]} times: '{phrase}'",
                )
            )

    # Grief inserted into tension/stealth beat.
    if GRIEF_PROMPT_RE.search(prompt) and not GRIEF_TEXT_RE.search(text) and TENSE_TEXT_RE.search(text):
        out.append(
            Finding(
                scene_id=sid,
                issue="emotion_mismatch_grief_in_tense_beat",
                severity="high",
                detail="prompt uses grief-heavy emotion while script beat is tense/stealth/confrontational.",
            )
        )

    # Generic action language in action-heavy script beats.
    if ACTION_TEXT_RE.search(text) and GENERIC_ACTION_PROMPT_RE.search(prompt):
        out.append(
            Finding(
                scene_id=sid,
                issue="action_subject_blur_risk",
                severity="medium",
                detail="script is action-specific, but prompt relies on generic movement template.",
            )
        )

    # Explicit cross-story name/place contamination.
    prompt_compact = re.sub(r"[\s_\-']", "", prompt_l)
    known_compact = {re.sub(r"[\s_\-']", "", k) for k in known_tokens}
    for token in CARRYOVER_TOKENS:
        token_l = token.lower()
        token_compact = re.sub(r"[\s_\-']", "", token_l)
        token_re = re.compile(rf"(?<![a-z0-9]){re.escape(token_l).replace('\\ ', r'[\\s_\\-]+')}(?![a-z0-9])", re.IGNORECASE)
        token_hit = bool(token_re.search(prompt_l))
        compact_hit = token_compact in prompt_compact
        matched = token_hit or (compact_hit and len(token_compact) >= 7)
        if matched and token_l not in known_tokens and token_compact not in known_compact:
            out.append(
                Finding(
                    scene_id=sid,
                    issue="carryover_proper_noun_risk",
                    severity="high",
                    detail=f"carry-over token detected: '{token}'",
                )
            )
            break

    # Continuity lock target should align with scene place.
    places = [str(x) for x in (scene.get("places") or []) if str(x)]
    m = CONTINUITY_LOCK_RE.search(prompt)
    if places and m:
        lock_target = str(m.group(1) or "").strip().lower()
        pid = places[0]
        expected = PLACE_EXPECTED_CUES.get(pid)
        if expected:
            _, cues = expected
            if not _contains_any(lock_target, cues):
                out.append(
                    Finding(
                        scene_id=sid,
                        issue="continuity_lock_place_mismatch",
                        severity="high",
                        detail=f"continuity lock target '{lock_target}' conflicts with scene place '{pid}'.",
                    )
                )
    return out


def _apply_repairs(scene: dict, findings: List[Finding]) -> bool:
    prompt = str(scene.get("llm_clip_prompt") or "")
    prompt_used = str(((scene.get("image") or {}).get("prompt_used")) or "")
    changed = False
    issues = {f.issue for f in findings}

    # Safe repair: remove known overused action template sentence.
    if "template_phrase_overused" in issues:
        old = "the rusty korean sickle turns in one compact arc and cuts through tough vines."
        for target in [old, old.capitalize()]:
            if target in prompt:
                prompt = prompt.replace(target, "the rusty Korean sickle is held ready in a controlled, tense posture.")
                changed = True
            if prompt_used and target in prompt_used:
                prompt_used = prompt_used.replace(target, "the rusty Korean sickle is held ready in a controlled, tense posture.")
                changed = True

    # Safe repair: replace grief sentence with neutral tension cue.
    if "emotion_mismatch_grief_in_tense_beat" in issues:
        for old in [
            "Tear-streaked eyes, trembling breath, and strained posture show visible grief.",
            "tear-streaked eyes, trembling breath, and strained posture show visible grief.",
        ]:
            if old in prompt:
                prompt = prompt.replace(old, "Tight jaw, guarded gaze, and restrained breathing convey tense realism.")
                changed = True
            if prompt_used and old in prompt_used:
                prompt_used = prompt_used.replace(old, "Tight jaw, guarded gaze, and restrained breathing convey tense realism.")
                changed = True

    if changed:
        scene["llm_clip_prompt"] = prompt
        if "image" in scene and isinstance(scene["image"], dict) and prompt_used:
            scene["image"]["prompt_used"] = prompt_used
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit semantic risks in clip prompts (carry-over/template/emotion/place/action-subject).")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = _load_project(args.story_id)
    scenes = [s for s in (data.get("scenes") or []) if isinstance(s, dict)]
    known_tokens = _collect_known_tokens(data)

    template_counts: Counter[str] = Counter()
    for s in scenes:
        p = str(s.get("llm_clip_prompt") or "").lower()
        for phrase in TEMPLATE_PHRASES:
            if phrase in p:
                template_counts[phrase] += 1

    by_scene: Dict[int, List[Finding]] = defaultdict(list)
    for s in scenes:
        sid = int(s.get("id") or 0)
        fs = _scene_findings(s, known_tokens, template_counts)
        by_scene[sid].extend(fs)

    changed_scenes = 0
    if args.apply:
        for s in scenes:
            sid = int(s.get("id") or 0)
            fs = by_scene.get(sid, [])
            if fs and _apply_repairs(s, fs):
                changed_scenes += 1
        if changed_scenes:
            p = ROOT / "work" / args.story_id / "out" / "project.json"
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    findings: List[Finding] = []
    for sid in sorted(by_scene.keys()):
        findings.extend(by_scene[sid])

    out_json = ROOT / "work" / args.story_id / "out" / "prompt_semantic_qc_candidates.json"
    out_md = ROOT / "work" / args.story_id / "out" / "prompt_semantic_qc_candidates.md"
    payload = {
        "story_id": args.story_id,
        "findings_total": len(findings),
        "scenes_flagged": sorted({f.scene_id for f in findings}),
        "changed_scenes": changed_scenes,
        "template_phrase_counts": dict(template_counts),
        "findings": [f.__dict__ for f in findings],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: List[str] = []
    lines.append(f"# prompt semantic QC candidates ({args.story_id})")
    lines.append("")
    lines.append(f"- findings_total: {len(findings)}")
    lines.append(f"- scenes_flagged: {len({f.scene_id for f in findings})}")
    lines.append(f"- changed_scenes: {changed_scenes}")
    lines.append("")
    lines.append("## template phrase counts")
    for k, v in template_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    grouped: Dict[int, List[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.scene_id].append(f)
    for sid in sorted(grouped.keys()):
        lines.append(f"## scene {sid}")
        for f in grouped[sid]:
            lines.append(f"- [{f.severity}] {f.issue}: {f.detail}")
        lines.append("")
    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "findings": len(findings), "changed_scenes": changed_scenes, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
