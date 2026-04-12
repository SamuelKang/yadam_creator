#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def make_mask(h: int, w: int, cx: int, cy: int) -> np.ndarray:
    s = max(8, int(min(h, w) * 0.015))
    m = np.zeros((h, w), np.uint8)
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], np.int32)
    cv2.fillConvexPoly(m, pts, 255)
    cv2.ellipse(m, (cx, cy), (int(s * 1.8), max(1, int(s * 0.58))), 0, 0, 360, 255, -1)
    cv2.ellipse(m, (cx, cy), (max(1, int(s * 0.58)), int(s * 1.8)), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 0.9)
    _, m = cv2.threshold(m, 42, 255, cv2.THRESH_BINARY)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--coords", default="work/story16/out/watermark_compare/manual_coords_clicked.json")
    ap.add_argument("--output", default="work/story16/clips_manual_clicked")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/manual_clicked_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)

    rows = json.loads(Path(args.coords).read_text(encoding="utf-8"))
    by_name = {r["file"]: r for r in rows}

    done = 0
    skipped = 0
    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]

        row = by_name.get(p.name)
        if row is None:
            cv2.imwrite(str(out_dir / p.name), img)
            skipped += 1
            continue

        cx, cy = int(row["cx"]), int(row["cy"])
        mask = make_mask(h, w, cx, cy)
        out = cv2.inpaint(img, mask, 2.8, cv2.INPAINT_TELEA)
        out = cv2.inpaint(out, make_mask(h, w, cx, cy), 1.9, cv2.INPAINT_TELEA)
        cv2.imwrite(str(out_dir / p.name), out)

        x0, y0 = int(w * 0.84), int(h * 0.80)
        ov = img.copy()
        cv2.circle(ov, (cx, cy), 3, (0, 0, 255), -1)
        co = img[y0:h, x0:w]
        cv = ov[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        tile = np.hstack([up(co), up(cv), up(cm), up(cn)])
        cv2.putText(tile, f"{p.name} click=({cx},{cy})", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(dbg_dir / p.name), tile)
        done += 1

    print(f"done: {done}, skipped(no coord): {skipped}")
    print(f"out: {out_dir}")
    print(f"debug: {dbg_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
