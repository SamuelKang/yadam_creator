#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[3]


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Check place reference images before clip stage")
    ap.add_argument("--story-id", required=True)
    args = ap.parse_args()

    project_path = ROOT / "work" / args.story_id / "out" / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"project.json not found: {project_path}")

    project = json.loads(project_path.read_text(encoding="utf-8"))
    issues: List[Dict[str, str]] = []

    for place in project.get("places", []) or []:
        if not isinstance(place, dict):
            continue
        name = str(place.get("name") or "").strip() or str(place.get("id") or "unknown")
        image_meta = place.get("image")
        if isinstance(image_meta, dict):
            _check_image_meta(name, image_meta, issues)
        else:
            issues.append(_issue("missing_meta", name, "place.image missing"))

    if not issues:
        print("OK: place reference metadata/files look ready for step 9")
        return 0

    print(f"FOUND {len(issues)} place reference issues")
    for row in issues:
        print(json.dumps(row, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
