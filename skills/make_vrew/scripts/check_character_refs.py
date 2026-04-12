#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[3]
GENERIC_ROLE_NAMES = {
    "나리", "도련님", "아씨", "아가씨", "스님", "노승", "승려",
    "아버지", "어머니", "아들", "딸", "소년", "소녀", "아이",
    "사내", "여인", "노인", "할머니", "할아버지", "박 서방",
}
LIKELY_HUMAN_ROLE_NAMES = {
    "나리", "도련님", "아씨", "아가씨", "스님", "노승", "승려",
    "아버지", "어머니", "아들", "딸", "소년", "소녀", "아이",
    "사내", "여인", "노인", "할머니", "할아버지", "사또", "부인", "대감",
}


def _issue(kind: str, label: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "label": label, "detail": detail}


def _check_image_meta(label: str, meta: Dict[str, Any], issues: List[Dict[str, str]]) -> None:
    status = str(meta.get("status") or "")
    path_text = str(meta.get("path") or "").strip()
    path = Path(path_text) if path_text else None

    if status != "ok":
        issues.append(_issue("status_not_ok", label, f"status={status}"))
        return

    if not path_text:
        issues.append(_issue("missing_path", label, "status=ok but path is empty"))
        return

    if not path or not path.exists():
        issues.append(_issue("missing_file", label, f"path missing: {path_text}"))
        return

    err_path = path.with_name(f"{path.stem}_error{path.suffix}")
    if err_path.exists():
        issues.append(_issue("stale_error_file", label, str(err_path)))


def _is_generic_role_name(name: str) -> bool:
    s = (name or "").strip()
    return s in GENERIC_ROLE_NAMES


def _looks_like_named_human(name: str) -> bool:
    s = (name or "").strip()
    if not s or _is_generic_role_name(s):
        return False
    if any(ch.isdigit() for ch in s):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Check character reference images before clip stage")
    ap.add_argument("--story-id", required=True)
    args = ap.parse_args()

    project_path = ROOT / "work" / args.story_id / "out" / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"project.json not found: {project_path}")

    project = json.loads(project_path.read_text(encoding="utf-8"))
    issues: List[Dict[str, str]] = []
    has_named_human = False

    for char in project.get("characters", []) or []:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name") or "").strip() or str(char.get("id") or "unknown")
        aliases = [str(x).strip() for x in (char.get("aliases") or []) if str(x).strip()]
        species = str(char.get("species") or "").strip()
        used_by_scenes = char.get("used_by_scenes") or []

        if _looks_like_named_human(name):
            has_named_human = True

        if _is_generic_role_name(name) and not aliases:
            issues.append(_issue("generic_canonical_name", name, "canonical name is only a role label and has no alias/real-name support"))

        if name in LIKELY_HUMAN_ROLE_NAMES and species and species != "인간":
            issues.append(_issue("species_mismatch", name, f"likely human role/name but species={species}"))

        if not used_by_scenes:
            issues.append(_issue("unused_character_ref", name, "reference exists but used_by_scenes is empty"))

        images = char.get("images")
        if isinstance(images, dict) and images:
            for variant, meta in images.items():
                if isinstance(meta, dict):
                    _check_image_meta(f"{name} [{variant}]", meta, issues)
        image_meta = char.get("image")
        if isinstance(image_meta, dict):
            _check_image_meta(name, image_meta, issues)

    if not has_named_human:
        issues.append(_issue("missing_named_protagonist_ref", args.story_id, "no non-generic human character reference found; clip identity consistency is unsafe"))

    if not issues:
        print("OK: character reference metadata/files look ready for step 9")
        return 0

    print(f"FOUND {len(issues)} character reference issues")
    for row in issues:
        print(json.dumps(row, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
