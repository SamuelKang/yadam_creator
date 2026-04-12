#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple


PLACE_EXPECTED_CUES: Dict[str, Tuple[str, List[str]]] = {
    "place_001": ("snowy mountain vista", ["snow mountain", "ridge", "valley", "frost landscape", "mountain vista"]),
    "place_002": ("village lane/market", ["village", "market", "lane", "street", "plaza", "square"]),
    "place_003": ("back-mountain path", ["back-mountain", "mountain path", "ridge path", "slope path", "pass"]),
    "place_004": ("magistrate office", ["magistrate", "court", "government office"]),
    "place_005": ("house exterior", ["house", "home", "residence", "roof", "gate", "exterior"]),
    "place_006": ("interior room", ["room", "interior", "chamber", "indoors"]),
    "place_007": ("house exterior", ["house exterior", "tile-roof house", "gate", "yard outside"]),
    "place_008": ("dark interior", ["room", "interior", "inner room", "shed", "barn", "cave", "indoors"]),
    "place_009": ("house courtyard", ["courtyard", "yard", "madang", "maru", "inside the wall"]),
    "place_010": ("gorge/cliff path", ["gorge", "cliff", "ravine", "ambush path", "mountain path"]),
}

PROTECT_RE = re.compile(r"(보호|shield|protect|blocking stance)", re.IGNORECASE)
LEDGER_TEXT_RE = re.compile(r"((?<!대)장부|\bledger\b|\baccount\s*book\b|\bbook of records\b)", re.IGNORECASE)
PREGNANCY_RE = re.compile(r"(임신|뱃속|태아|손주|unborn|pregnan)", re.IGNORECASE)
WARDROBE_TRANSITION_RE = re.compile(r"(환복|갈아입|바꿔입|치료|붕대[를 ]?풀|bandage removed|changed clothes|new outfit)", re.IGNORECASE)
SHIM_GAUNT_FACE_CUES = ["gaunt face", "gaunt", "hollow-cheeked", "angular face"]
SHIM_ROUND_FACE_CUES = ["round face", "round-faced", "plump face", "full cheeks", "chubby cheeks"]


@dataclass
class Finding:
    scene_id: int
    issue: str
    severity: str
    detail: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _contains_any(haystack: str, needles: List[str]) -> bool:
    h = (haystack or "").lower()
    return any(n.lower() in h for n in needles)


def _append_clause(prompt: str, clause: str) -> str:
    p = _norm(prompt)
    if clause.lower() in p.lower():
        return p
    if not p.endswith("."):
        p += "."
    return f"{p} {clause}"


def _detect_shim_ids(data: dict) -> Set[str]:
    ids: Set[str] = set()
    for c in data.get("characters", []):
        cid = str(c.get("id") or "")
        nm = str(c.get("name") or c.get("name_ko") or "")
        if cid and ("심" in nm or "shim" in nm.lower()):
            ids.add(cid)
    return ids


def _scan_scene(scene: dict, shim_ids: Set[str]) -> List[Finding]:
    findings: List[Finding] = []
    sid = int(scene.get("id") or 0)
    text = scene.get("text") or ""
    prompt = scene.get("llm_clip_prompt") or ""
    prompt_l = prompt.lower()
    places = scene.get("places") or []
    chars = set(scene.get("characters") or [])

    for pid in places:
        if pid not in PLACE_EXPECTED_CUES:
            continue
        label, cues = PLACE_EXPECTED_CUES[pid]
        if not _contains_any(prompt, cues):
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="place_context_drift",
                    severity="medium",
                    detail=f"place={pid}({label}) but prompt lacks expected location cues {cues}",
                )
            )

    has_shim = any(cid in chars for cid in shim_ids) or "shim" in prompt_l
    has_yeonhwa = "char_007" in chars or "yeonhwa" in prompt_l

    if LEDGER_TEXT_RE.search(text):
        if has_shim and "shim" not in prompt_l:
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="role_missing_shim_in_ledger_scene",
                    severity="high",
                    detail="scene text indicates ledger beat but prompt does not include Shim.",
                )
            )
        if has_yeonhwa and re.search(r"yeonhwa.{0,36}(ledger|book)|(?:ledger|book).{0,36}yeonhwa", prompt_l):
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="role_ledger_holder_drift",
                    severity="high",
                    detail="prompt implies Yeonhwa holds ledger/book.",
                )
            )
        if "held only by shim" not in prompt_l:
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="role_ledger_owner_lock_missing",
                    severity="medium",
                    detail="ledger ownership lock phrase is missing.",
                )
            )

    if PROTECT_RE.search(text) and not _contains_any(prompt, ["shield", "protect", "blocks", "stands in front"]):
        findings.append(
            Finding(
                scene_id=sid,
                issue="role_protection_action_missing",
                severity="medium",
                detail="scene text is protective, but prompt lacks explicit protective blocking action.",
            )
        )

    if _contains_any(prompt, ["shim", "yeonhwa"]) and "gat" in prompt_l and "no gat" not in prompt_l:
        findings.append(
            Finding(
                scene_id=sid,
                issue="wardrobe_female_gat_drift",
                severity="high",
                detail="female character may be rendered with gat unless explicitly constrained.",
            )
        )

    if PREGNANCY_RE.search(text) and _contains_any(prompt, ["baby in arms", "infant in arms", "holding a baby"]):
        findings.append(
            Finding(
                scene_id=sid,
                issue="prop_pregnancy_baby_conflict",
                severity="high",
                detail="pregnancy beat conflicts with baby-in-arms depiction.",
            )
        )

    if has_shim:
        if _contains_any(prompt, SHIM_ROUND_FACE_CUES):
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="shim_round_face_drift",
                    severity="high",
                    detail="Shim face anchor drifted to round/plump wording.",
                )
            )
        if not _contains_any(prompt, SHIM_GAUNT_FACE_CUES):
            findings.append(
                Finding(
                    scene_id=sid,
                    issue="shim_face_anchor_missing",
                    severity="medium",
                    detail="Shim appears but gaunt-face anchor is missing.",
                )
            )

    return findings


def _scan_adjacent_shim_continuity(scenes: List[dict], shim_ids: Set[str]) -> List[Finding]:
    out: List[Finding] = []
    ordered = sorted(scenes, key=lambda x: int(x.get("id") or 0))
    for prev, curr in zip(ordered, ordered[1:]):
        pid = int(prev.get("id") or 0)
        cid = int(curr.get("id") or 0)
        if cid - pid > 2:
            continue
        prev_chars = set(prev.get("characters") or [])
        curr_chars = set(curr.get("characters") or [])
        if not (any(x in prev_chars for x in shim_ids) and any(x in curr_chars for x in shim_ids)):
            continue
        prev_places = set(prev.get("places") or [])
        curr_places = set(curr.get("places") or [])
        if prev_places and curr_places and prev_places.isdisjoint(curr_places):
            continue
        combined_text = f"{prev.get('text') or ''} {curr.get('text') or ''}"
        if WARDROBE_TRANSITION_RE.search(combined_text):
            continue
        p_prev = (prev.get("llm_clip_prompt") or "").lower()
        p_curr = (curr.get("llm_clip_prompt") or "").lower()
        if ("bandage" in p_prev or "붕대" in p_prev) and ("bandage" not in p_curr and "붕대" not in p_curr):
            out.append(
                Finding(
                    scene_id=cid,
                    issue="shim_wardrobe_continuity_risk",
                    severity="medium",
                    detail=f"Shim bandage cue appears in scene {pid} but disappears in adjacent scene {cid} without transition cue.",
                )
            )
    return out


def _apply_scene_repairs(scene: dict, scene_findings: List[Finding]) -> bool:
    prompt = scene.get("llm_clip_prompt") or ""
    prompt_used = ((scene.get("image") or {}).get("prompt_used")) or ""
    changed = False

    issues = {f.issue for f in scene_findings}
    places = scene.get("places") or []

    if "wardrobe_female_gat_drift" in issues:
        clause = "No gat, no male hat, and no male headgear on any female character."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "prop_pregnancy_baby_conflict" in issues:
        clause = "No baby in arms, no infant carried, unborn child only."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "role_ledger_holder_drift" in issues or "role_ledger_owner_lock_missing" in issues:
        clause = "Ledger ownership is explicit and fixed in this scene; no transfer to other characters."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "role_protection_action_missing" in issues:
        clause = "One character stands in front to shield another in a protective blocking stance."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "place_context_drift" in issues and places:
        pid = places[0]
        label = PLACE_EXPECTED_CUES.get(pid, ("scene location", []))[0]
        clause = f"Setting continuity lock: keep this scene at the same {label}."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "shim_round_face_drift" in issues:
        clause = "Avoid round or plump facial shape for Shim; keep gaunt facial structure."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "shim_face_anchor_missing" in issues:
        clause = "Shim must keep a gaunt face and tightly controlled posture."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if "shim_wardrobe_continuity_risk" in issues:
        clause = "Continuity lock: keep Shim's same outfit and head-bandage state as adjacent scenes in this beat."
        p2 = _append_clause(prompt, clause)
        u2 = _append_clause(prompt_used, clause) if prompt_used else prompt_used
        changed = changed or (p2 != prompt) or (u2 != prompt_used)
        prompt, prompt_used = p2, u2

    if changed:
        scene["llm_clip_prompt"] = prompt
        if "image" in scene and isinstance(scene["image"], dict) and prompt_used:
            scene["image"]["prompt_used"] = prompt_used
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Detect (and optionally patch) role/place/wardrobe-prop drift in llm_clip_prompt/image.prompt_used."
    )
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    pj = Path(f"work/{args.story_id}/out/project.json")
    if not pj.exists():
        raise SystemExit(f"missing: {pj}")
    data = json.loads(pj.read_text(encoding="utf-8"))
    shim_ids = _detect_shim_ids(data)

    findings: List[Finding] = []
    scene_map: Dict[int, List[Finding]] = {}
    for s in data.get("scenes", []):
        fs = _scan_scene(s, shim_ids)
        if not fs:
            continue
        findings.extend(fs)
        scene_map[int(s.get("id") or 0)] = fs
    adj = _scan_adjacent_shim_continuity(data.get("scenes", []), shim_ids)
    for f in adj:
        findings.append(f)
        scene_map.setdefault(f.scene_id, []).append(f)

    changed_scenes = 0
    if args.apply and scene_map:
        for s in data.get("scenes", []):
            sid = int(s.get("id") or 0)
            if sid in scene_map and _apply_scene_repairs(s, scene_map[sid]):
                changed_scenes += 1
        if changed_scenes:
            pj.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_json = Path(f"work/{args.story_id}/out/role_place_prop_qc_candidates.json")
    out_md = Path(f"work/{args.story_id}/out/role_place_prop_qc_candidates.md")
    out_json.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "story_id": args.story_id,
        "findings_total": len(findings),
        "scenes_flagged": sorted(scene_map.keys()),
        "changed_scenes": changed_scenes,
        "findings": [f.__dict__ for f in findings],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# role/place/wardrobe-prop QC candidates ({args.story_id})",
        "",
        f"- findings_total: {len(findings)}",
        f"- scenes_flagged: {len(scene_map)}",
        f"- changed_scenes: {changed_scenes}",
        "",
    ]
    by_scene: Dict[int, List[Finding]] = {}
    for f in findings:
        by_scene.setdefault(f.scene_id, []).append(f)
    for sid in sorted(by_scene.keys()):
        lines.append(f"## scene {sid}")
        for f in by_scene[sid]:
            lines.append(f"- [{f.severity}] {f.issue}: {f.detail}")
        lines.append("")
    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "findings": len(findings), "changed_scenes": changed_scenes, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
