#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[3]


def _issue(kind: str, scene_id: int, detail: str) -> Dict[str, Any]:
    return {"kind": kind, "scene_id": scene_id, "detail": detail}


def _analyze_brightness(path: Path) -> Dict[str, float]:
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        small = rgb.resize((128, 128))
        stat = ImageStat.Stat(small)
        mean = sum(stat.mean) / 3.0
        px = small.load()
        width, height = small.size
        white_pixels = 0
        bright_pixels = 0
        for y in range(height):
            for x in range(width):
                r, g, b = px[x, y]
                if r >= 245 and g >= 245 and b >= 245:
                    white_pixels += 1
                if r >= 230 and g >= 230 and b >= 230:
                    bright_pixels += 1
        total = max(1, width * height)
        return {
            "mean": mean,
            "white_ratio": white_pixels / total,
            "bright_ratio": bright_pixels / total,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check clip images before export")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--white-ratio-threshold", type=float, default=0.70)
    ap.add_argument("--mean-threshold", type=float, default=238.0)
    args = ap.parse_args()

    project_path = ROOT / "work" / args.story_id / "out" / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"project.json not found: {project_path}")

    project = json.loads(project_path.read_text(encoding="utf-8"))
    issues: List[Dict[str, Any]] = []

    for scene in project.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue
        sid = int(scene.get("id") or 0)
        meta = scene.get("image")
        if not isinstance(meta, dict):
            issues.append(_issue("missing_meta", sid, "scene.image missing"))
            continue
        status = str(meta.get("status") or "")
        path_text = str(meta.get("path") or "").strip()
        if status != "ok":
            issues.append(_issue("status_not_ok", sid, f"status={status}"))
            continue
        if not path_text:
            issues.append(_issue("missing_path", sid, "status=ok but path empty"))
            continue
        path = Path(path_text)
        if not path.exists():
            issues.append(_issue("missing_file", sid, path_text))
            continue
        err_path = path.with_name(f"{path.stem}_error{path.suffix}")
        if err_path.exists():
            issues.append(_issue("stale_error_file", sid, str(err_path)))
        metrics = _analyze_brightness(path)
        if (
            metrics["white_ratio"] >= float(args.white_ratio_threshold)
            and metrics["mean"] >= float(args.mean_threshold)
        ):
            issues.append(
                _issue(
                    "suspected_white_background",
                    sid,
                    f"mean={metrics['mean']:.1f}, white_ratio={metrics['white_ratio']:.2f}, bright_ratio={metrics['bright_ratio']:.2f}",
                )
            )

    if not issues:
        print("OK: clip images look ready for export")
        return 0

    print(f"FOUND {len(issues)} clip image issues")
    for row in issues:
        print(json.dumps(row, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
