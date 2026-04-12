#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def build_mask(h: int, w: int, cx: int, cy: int, base: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    s = max(7, int(base))
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], np.int32)
    cv2.fillConvexPoly(m, pts, 255)
    cv2.ellipse(m, (cx, cy), (int(s * 1.9), max(1, int(s * 0.58))), 0, 0, 360, 255, -1)
    cv2.ellipse(m, (cx, cy), (max(1, int(s * 0.58)), int(s * 1.9)), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 0.9)
    _, m = cv2.threshold(m, 42, 255, cv2.THRESH_BINARY)
    return m


def residual_score(img: np.ndarray, cx: int, cy: int, base: int) -> tuple[float, np.ndarray]:
    h, w = img.shape[:2]
    m1 = build_mask(h, w, cx, cy, base)
    out = cv2.inpaint(img, m1, 2.8, cv2.INPAINT_TELEA)

    # score on ROI around center: penalize bright unsaturated sparkle and hard edges
    r = max(12, int(base * 1.6))
    x0, y0 = max(0, cx - r), max(0, cy - r)
    x1, y1 = min(w, cx + r + 1), min(h, cy + r + 1)
    roi = out[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)

    bright = ((hsv[:, :, 2] > 168) & (hsv[:, :, 1] < 90)).mean()
    grad = cv2.Laplacian(gray, cv2.CV_32F)
    edge = float(np.mean(np.abs(grad)))

    # compare with nearby ring texture continuity
    rr = max(r + 6, int(base * 2.2))
    xx0, yy0 = max(0, cx - rr), max(0, cy - rr)
    xx1, yy1 = min(w, cx + rr + 1), min(h, cy + rr + 1)
    patch = out[yy0:yy1, xx0:xx1]
    pg = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    pg_blur = cv2.GaussianBlur(pg, (0, 0), 2.0)
    texture = float(np.mean(np.abs(pg - pg_blur)))

    score = bright * 5.0 + edge * 0.020 + texture * 0.010
    return score, out


def choose_best(img: np.ndarray, cx0: int, cy0: int, base: int) -> tuple[int, int, np.ndarray, float]:
    best_score = 1e9
    best = (cx0, cy0)
    best_img = img

    # coarse then fine search
    steps = [max(2, int(base * 0.45)), 1]
    center = (cx0, cy0)
    for step in steps:
        cxc, cyc = center
        candidates = []
        for dy in range(-3 * step, 3 * step + 1, step):
            for dx in range(-3 * step, 3 * step + 1, step):
                candidates.append((cxc + dx, cyc + dy))

        local_best_score = 1e9
        local_best = center
        local_img = best_img
        for cx, cy in candidates:
            s, out = residual_score(img, cx, cy, base)
            if s < local_best_score:
                local_best_score = s
                local_best = (cx, cy)
                local_img = out

        center = local_best
        if local_best_score < best_score:
            best_score = local_best_score
            best = local_best
            best_img = local_img

    return best[0], best[1], best_img, float(best_score)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--coords", default="work/story16/out/watermark_compare/manual_coords.json")
    ap.add_argument("--output", default="work/story16/clips_manual_coords_refined")
    ap.add_argument("--coords-out", default="work/story16/out/watermark_compare/manual_coords_refined.json")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/manual_coords_refined_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)

    coords = json.loads(Path(args.coords).read_text(encoding="utf-8"))
    rows_out = []

    for row in coords:
        name = row["file"]
        img = cv2.imread(str(in_dir / name), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        cx0, cy0 = int(row["cx"]), int(row["cy"])
        base = max(8, int(min(h, w) * 0.015))

        cx, cy, out, sc = choose_best(img, cx0, cy0, base)
        cv2.imwrite(str(out_dir / name), out)

        row2 = dict(row)
        row2["cx_initial"] = cx0
        row2["cy_initial"] = cy0
        row2["cx"] = int(cx)
        row2["cy"] = int(cy)
        row2["refine_score"] = float(sc)
        rows_out.append(row2)

        # debug
        m = build_mask(h, w, cx, cy, base)
        x0, y0 = int(w * 0.84), int(h * 0.80)
        ov = img.copy()
        cv2.circle(ov, (cx0, cy0), 3, (255, 0, 255), -1)
        cv2.circle(ov, (cx, cy), 3, (0, 0, 255), -1)
        co = img[y0:h, x0:w]
        cv = ov[y0:h, x0:w]
        cm = cv2.cvtColor(m[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        tile = np.hstack([up(co), up(cv), up(cm), up(cn)])
        cv2.putText(
            tile,
            f"{name} init=({cx0},{cy0}) final=({cx},{cy}) score={sc:.3f}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(dbg_dir / name), tile)

    Path(args.coords_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.coords_out).write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {len(rows_out)}")
    print(f"out: {out_dir}")
    print(f"coords_out: {args.coords_out}")
    print(f"debug: {dbg_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
