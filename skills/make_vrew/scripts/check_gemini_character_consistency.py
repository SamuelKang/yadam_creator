#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_TERMS = [
    "korean manhwa/webtoon look",
    "korean webtoon",
    "한국 웹툰 스타일",
    "정돈된 캐릭터 디자인풍",
    "균일한 2d 셀 셰이딩",
    "a tense moment unfolds in silence",
    "no central character appears",
]

GENERIC_SUBJECTS = {"village residents", "joseon-era villagers", "villagers"}
COMMON_NON_PROPER = {
    "마을",
    "집",
    "마당",
    "방",
    "산",
    "여인",
    "노파",
    "머슴",
    "장정",
    "할멈",
    "주민",
    "사람들",
    "아낙",
    "아낙들",
    "사내",
    "관아",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _load_project(story_id: str) -> Tuple[Path, Dict[str, Any]]:
    path = ROOT / "work" / story_id / "out" / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"missing project.json: {path}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _extract_subjects(prompt: str) -> List[str]:
    m = re.search(r"Primary subjects:\s*(.*?)\.\s*Visible action:", prompt, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    parts = [_norm(x).lower() for x in raw.split(",") if _norm(x)]
    return parts


def _extract_place(prompt: str) -> str:
    m = re.search(r"\sat\s([^.]+)\.\s+Primary subjects:", prompt)
    return _norm(m.group(1)) if m else ""


def _scene_range_ok(sid: int, start: int, end: int | None) -> bool:
    if sid < start:
        return False
    if end is not None and sid > end:
        return False
    return True


def _contains_token(text: str, token: str) -> bool:
    if not token:
        return False
    t = token.strip()
    if not t:
        return False
    if re.fullmatch(r"[A-Za-z0-9 _\-']+", t):
        return bool(re.search(rf"\b{re.escape(t)}\b", text, flags=re.IGNORECASE))
    return t in text


def audit_story(project: Dict[str, Any], start: int, end: int | None) -> Dict[str, Any]:
    scenes = [s for s in (project.get("scenes") or []) if isinstance(s, dict)]

    char_tokens: List[str] = []
    for c in (project.get("characters") or []):
        if not isinstance(c, dict):
            continue
        for tok in [c.get("name")] + list(c.get("aliases") or []):
            ts = _norm(tok)
            if len(ts) >= 2 and ts not in COMMON_NON_PROPER:
                char_tokens.append(ts)

    place_tokens: List[str] = []
    for p in (project.get("places") or []):
        if not isinstance(p, dict):
            continue
        ps = _norm(p.get("name"))
        if len(ps) >= 2 and ps not in COMMON_NON_PROPER:
            place_tokens.append(ps)

    items: List[Dict[str, Any]] = []
    severe = 0
    warning = 0

    for idx, sc in enumerate(scenes, start=1):
        sid = int(sc.get("id") or idx)
        if not _scene_range_ok(sid, start, end):
            continue

        text = _norm(sc.get("text") or "")
        prompt = _norm(sc.get("llm_clip_prompt") or "")
        prompt_used = _norm(((sc.get("image") or {}).get("prompt_used") or ""))
        scene_chars = [str(x) for x in (sc.get("characters") or []) if str(x).strip()]

        issues: List[str] = []
        level = "ok"

        if not prompt:
            issues.append("empty_llm_clip_prompt")
        if prompt != prompt_used:
            issues.append("prompt_not_synced")

        low = prompt.lower()
        for term in FORBIDDEN_TERMS:
            if term in low:
                issues.append(f"forbidden_term:{term}")

        if '"' in prompt or "'" in prompt:
            issues.append("quote_mark_in_prompt")

        subjects = _extract_subjects(prompt)
        if not subjects:
            issues.append("missing_primary_subjects")
        else:
            seen = set()
            dup = False
            for s in subjects:
                if s in seen:
                    dup = True
                    break
                seen.add(s)
            if dup:
                issues.append("duplicated_subject_entries")

        if scene_chars and subjects and all(s in GENERIC_SUBJECTS for s in subjects):
            issues.append("scene_has_characters_but_subjects_generic")

        if re.search(r'[\"“”‘’].+[\"“”‘’]', text) and subjects and len(subjects) == 1 and subjects[0] in GENERIC_SUBJECTS:
            issues.append("dialogue_scene_single_subject_but_generic")

        # unknown proper nouns in current prompt values (costly drift source)
        for tok in char_tokens + place_tokens:
            if _contains_token(prompt, tok):
                issues.append(f"proper_noun_in_prompt:{tok}")
                break

        place = _extract_place(prompt)
        if place == "절" and not any(k in text for k in ["절", "산신당", "사찰", "법당"]):
            issues.append("likely_place_mismatch:temple")
        if place == "산" and not any(k in text for k in ["산", "산길", "비탈", "뒷산", "절벽"]):
            issues.append("likely_place_mismatch:mountain")
        if place == "집" and not any(k in text for k in ["집", "초막", "곳간", "안채", "툇마루", "아궁이"]):
            issues.append("likely_place_mismatch:house")
        if place == "마당" and not any(k in text for k in ["마당", "대문", "담장", "행랑", "장독대", "곳간 문 앞"]):
            issues.append("likely_place_mismatch:yard")

        severe_prefix = (
            "empty_",
            "prompt_not_synced",
            "forbidden_term:",
            "quote_mark_in_prompt",
            "missing_primary_subjects",
            "duplicated_subject_entries",
            "scene_has_characters_but_subjects_generic",
        )
        if issues:
            if any(i.startswith(severe_prefix) for i in issues):
                level = "severe"
                severe += 1
            else:
                level = "warning"
                warning += 1

        items.append({
            "scene_id": sid,
            "level": level,
            "issues": issues,
            "place": place,
            "subjects": subjects,
        })

    return {
        "summary": {
            "total": len(items),
            "severe": severe,
            "warning": warning,
            "ok": max(0, len(items) - severe - warning),
        },
        "items": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Gemini clip prompt character consistency before generation")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--start-scene", type=int, default=1)
    ap.add_argument("--end-scene", type=int, default=None)
    ap.add_argument("--strict", action="store_true", help="return non-zero if severe issues exist")
    args = ap.parse_args()

    _, project = _load_project(args.story_id)
    audit = audit_story(project, args.start_scene, args.end_scene)

    out_path = ROOT / "work" / args.story_id / "out" / "gemini_character_consistency_audit.json"
    out_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"saved: {out_path}")
    print(json.dumps(audit["summary"], ensure_ascii=False))

    if args.strict and int(audit["summary"]["severe"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
