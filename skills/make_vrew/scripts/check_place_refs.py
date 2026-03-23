#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image


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


def _check_border_edges(
    label: str,
    image_path: Path,
    issues: List[Dict[str, str]],
    edge_band: int,
    side_threshold: float,
) -> None:
    """
    Detect black/white frame bars on all four sides.
    A side is flagged when near-black or near-white ratio exceeds side_threshold.
    """
    try:
        arr = np.array(Image.open(image_path).convert("RGB"))
    except Exception as e:
        issues.append(_issue("image_open_error", label, f"{image_path}: {e}"))
        return

    if arr.ndim != 3 or arr.shape[2] != 3:
        issues.append(_issue("invalid_image_shape", label, f"{image_path}: shape={arr.shape}"))
        return

    h, w, _ = arr.shape
    b = max(1, min(int(edge_band), max(1, min(h, w) // 8)))
    sides = {
        "top": arr[:b, :, :].reshape(-1, 3),
        "bottom": arr[-b:, :, :].reshape(-1, 3),
        "left": arr[:, :b, :].reshape(-1, 3),
        "right": arr[:, -b:, :].reshape(-1, 3),
    }

    def _ratio_black(px: np.ndarray) -> float:
        return float(((px[:, 0] < 16) & (px[:, 1] < 16) & (px[:, 2] < 16)).mean())

    def _ratio_white(px: np.ndarray) -> float:
        return float(((px[:, 0] > 239) & (px[:, 1] > 239) & (px[:, 2] > 239)).mean())

    for side, px in sides.items():
        black_ratio = _ratio_black(px)
        white_ratio = _ratio_white(px)

        if black_ratio >= side_threshold:
            issues.append(
                _issue(
                    f"black_border_{side}",
                    label,
                    f"path={image_path} side={side} black_ratio={black_ratio:.3f} (threshold={side_threshold:.2f})",
                )
            )
        if white_ratio >= side_threshold:
            issues.append(
                _issue(
                    f"white_border_{side}",
                    label,
                    f"path={image_path} side={side} white_ratio={white_ratio:.3f} (threshold={side_threshold:.2f})",
                )
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="Check place reference images before clip stage")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--edge-band", type=int, default=4, help="border sample width in pixels (default: 4)")
    ap.add_argument(
        "--border-threshold",
        type=float,
        default=0.85,
        help="flag when near-black/near-white ratio on a side exceeds this value (default: 0.85)",
    )
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
            path_text = str(image_meta.get("path") or "").strip()
            if str(image_meta.get("status") or "") == "ok" and path_text:
                _check_border_edges(
                    name,
                    Path(path_text),
                    issues,
                    edge_band=int(args.edge_band),
                    side_threshold=float(args.border_threshold),
                )
        else:
            issues.append(_issue("missing_meta", name, "place.image missing"))

    if not issues:
        print("OK: place reference metadata/files and border-edge checks look ready for step 9")
        return 0

    print(f"FOUND {len(issues)} place reference issues")
    for row in issues:
        print(json.dumps(row, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
