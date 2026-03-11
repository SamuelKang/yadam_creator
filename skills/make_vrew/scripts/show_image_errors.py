from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _iter_character_errors(project: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    for c in project.get("characters", []) or []:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        images = c.get("images")
        if isinstance(images, dict) and images:
            for variant, meta in images.items():
                if not isinstance(meta, dict):
                    continue
                if str(meta.get("status") or "") != "ok":
                    yield ("character", f"{name} [{variant}]", meta)
        else:
            meta = c.get("image")
            if isinstance(meta, dict) and str(meta.get("status") or "") != "ok":
                yield ("character", name, meta)


def _iter_place_errors(project: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    for p in project.get("places", []) or []:
        if not isinstance(p, dict):
            continue
        meta = p.get("image")
        if isinstance(meta, dict) and str(meta.get("status") or "") != "ok":
            yield ("place", str(p.get("name") or ""), meta)


def _iter_clip_errors(project: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    for s in project.get("scenes", []) or []:
        if not isinstance(s, dict):
            continue
        meta = s.get("image")
        if isinstance(meta, dict) and str(meta.get("status") or "") != "ok":
            yield ("clip", f"scene {int(s.get('id', 0)):03d}", meta)


def _summarize_errors(rows: List[Tuple[str, str, Dict[str, Any]]]) -> str:
    if not rows:
        return "[INFO] no image errors found"
    lines = [f"[INFO] image errors: {len(rows)}"]
    for kind, label, meta in rows:
        status = str(meta.get("status") or "")
        err = str(meta.get("last_error") or "")
        attempts = int(meta.get("attempts") or 0)
        lines.append(f"- {kind}: {label} | status={status} | attempts={attempts} | error={err}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Show image generation errors from work/<story-id>/out/project.json")
    ap.add_argument("--story-id", required=True, help="예: story14")
    ap.add_argument("--project-root", default=".", help="프로젝트 루트(기본: 현재 폴더)")
    ap.add_argument(
        "--include-clips",
        action="store_true",
        help="clip 이미지 에러도 함께 표시",
    )
    args = ap.parse_args()

    project_path = Path(args.project_root).resolve() / "work" / args.story_id / "out" / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"project.json 이 없습니다: {project_path}")

    project = json.loads(project_path.read_text(encoding="utf-8"))
    rows: List[Tuple[str, str, Dict[str, Any]]] = []
    rows.extend(_iter_character_errors(project))
    rows.extend(_iter_place_errors(project))
    if args.include_clips:
        rows.extend(_iter_clip_errors(project))
    print(_summarize_errors(rows))


if __name__ == "__main__":
    main()
