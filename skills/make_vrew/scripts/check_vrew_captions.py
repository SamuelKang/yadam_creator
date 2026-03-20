#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Inspect exported .vrew captions for multi-line overflow.")
    ap.add_argument("--story-id", required=True, help="story id like story14")
    ap.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="repo root (default: autodetect from script path)",
    )
    ap.add_argument("--max-lines", type=int, default=2, help="max allowed caption lines (default: 2)")
    ap.add_argument(
        "--line-max-chars",
        type=int,
        default=24,
        help="soft max chars per rendered line for review (default: 24)",
    )
    ap.add_argument("--limit", type=int, default=30, help="max suspicious clips to print (default: 30)")
    return ap.parse_args()


def _load_vrew_project(vrew_path: Path) -> dict:
    with zipfile.ZipFile(vrew_path, "r") as zf:
        return json.loads(zf.read("project.json"))


def _collect_audio_names(project: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in project.get("files", []):
        if not isinstance(entry, dict):
            continue
        media_id = str(entry.get("mediaId") or "").strip()
        name = str(entry.get("name") or "").strip()
        if media_id and name:
            out[media_id] = name
    return out


def _extract_caption_text(clip: dict) -> str:
    captions = clip.get("captions") or []
    if not isinstance(captions, list):
        return ""
    inserts: list[str] = []
    for caption in captions:
        if not isinstance(caption, dict):
            continue
        text_items = caption.get("text") or []
        if not isinstance(text_items, list):
            continue
        for item in text_items:
            if isinstance(item, dict):
                inserts.append(str(item.get("insert") or ""))
    return "".join(inserts).strip()


def _extract_media_id(clip: dict) -> str:
    words = clip.get("words") or []
    if not isinstance(words, list):
        return ""
    for word in words:
        if not isinstance(word, dict):
            continue
        media_id = str(word.get("mediaId") or "").strip()
        if media_id:
            return media_id
    return ""


def main() -> int:
    args = _parse_args()
    root = Path(args.project_root).resolve()
    vrew_path = root / "work" / args.story_id / "out" / f"{args.story_id}.vrew"
    if not vrew_path.exists():
        print(f"[ERROR] vrew file not found: {vrew_path}")
        return 2

    project = _load_vrew_project(vrew_path)
    audio_names = _collect_audio_names(project)
    clips = (((project.get("transcript") or {}).get("scenes") or [{}])[0].get("clips") or [])
    if not isinstance(clips, list):
        print("[ERROR] invalid vrew transcript structure")
        return 2

    suspicious: list[str] = []
    for idx, clip in enumerate(clips, start=1):
        if not isinstance(clip, dict):
            continue
        caption_text = _extract_caption_text(clip)
        lines = [line.strip() for line in caption_text.splitlines() if line.strip()]
        if not lines:
            continue
        max_line_len = max(len(line) for line in lines)
        media_id = _extract_media_id(clip)
        audio_name = audio_names.get(media_id, "")
        match = re.search(r"scene_(\d+)_(\d+)", audio_name)
        label = f"clip#{idx}"
        if match:
            label = f"scene {int(match.group(1)):03d} chunk {int(match.group(2)):03d}"
        if len(lines) > max(1, int(args.max_lines)) or max_line_len > max(1, int(args.line_max_chars)):
            preview = " / ".join(lines)
            suspicious.append(
                f"{label}: lines={len(lines)}, max_line_chars={max_line_len}, text={preview}"
            )

    if suspicious:
        print(
            f"[WARN] suspicious captions found: {len(suspicious)} "
            f"(max_lines={args.max_lines}, line_max_chars={args.line_max_chars})"
        )
        for row in suspicious[: max(1, int(args.limit))]:
            print(f"- {row}")
        if len(suspicious) > int(args.limit):
            print(f"- ... {len(suspicious) - int(args.limit)} more")
        return 1

    print(
        f"[OK] captions look within limits "
        f"(max_lines={args.max_lines}, line_max_chars={args.line_max_chars})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
