#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def _star_mask(h: int, w: int, cx: int, cy: int, size: float) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    s = max(6, int(size))
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], np.int32)
    cv2.fillConvexPoly(m, pts, 255)
    cv2.ellipse(m, (cx, cy), (int(s * 1.8), max(1, int(s * 0.55))), 0, 0, 360, 255, -1)
    cv2.ellipse(m, (cx, cy), (max(1, int(s * 0.55)), int(s * 1.8)), 0, 0, 360, 255, -1)
    return m


def _top_peaks(score: np.ndarray, k: int, min_dist: int, min_val: float) -> list[tuple[int, int, float]]:
    s = score.copy()
    pts: list[tuple[int, int, float]] = []
    for _ in range(k):
        iy, ix = np.unravel_index(np.argmax(s), s.shape)
        v = float(s[iy, ix])
        if v < min_val:
            break
        pts.append((int(ix), int(iy), v))
        x0 = max(0, ix - min_dist)
        x1 = min(s.shape[1], ix + min_dist + 1)
        y0 = max(0, iy - min_dist)
        y1 = min(s.shape[0], iy + min_dist + 1)
        s[y0:y1, x0:x1] = -1.0
    return pts


def detect_residual_peaks(img: np.ndarray) -> list[tuple[int, int, float]]:
    h, w = img.shape[:2]
    x0, y0 = int(w * 0.82), int(h * 0.80)
    roi = img[y0:h, x0:w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    wh = (hsv[:, :, 2].astype(np.float32) / 255.0) * (1.0 - hsv[:, :, 1].astype(np.float32) / 255.0)
    hp = np.clip(gray - cv2.GaussianBlur(gray, (0, 0), 2.0), 0, None) / 255.0
    base = wh * 0.9 + hp * 1.25

    # 1) lower-band peaks (captures most watermark placements)
    lower = base.copy()
    gate_lower = np.zeros_like(lower, np.float32)
    ygate = int(0.88 * h - y0)
    gate_lower[max(0, ygate):, :] = 1.0
    lower *= gate_lower
    lower_pts = _top_peaks(lower, k=3, min_dist=max(10, int(min(h, w) * 0.02)), min_val=0.08)

    # 2) center-prior peak (catches misses around mid-lower right)
    yy, xx = np.mgrid[0:base.shape[0], 0:base.shape[1]]
    ex = int(0.90 * w) - x0
    ey = int(0.90 * h) - y0
    dist = np.sqrt((xx - ex) ** 2 + (yy - ey) ** 2)
    prior = np.exp(-(dist ** 2) / (2.0 * (0.12 * min(h, w)) ** 2)).astype(np.float32)
    guided = base + prior * 0.35
    guide_pts = _top_peaks(guided, k=1, min_dist=max(10, int(min(h, w) * 0.02)), min_val=0.05)

    out: list[tuple[int, int, float]] = []
    used: set[tuple[int, int]] = set()
    for ix, iy, v in (lower_pts + guide_pts):
        gx, gy = x0 + ix, y0 + iy
        key = (gx // 6, gy // 6)
        if key in used:
            continue
        used.add(key)
        out.append((gx, gy, v))
    return out


def process_image(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, float]]]:
    h, w = img.shape[:2]
    peaks = detect_residual_peaks(img)

    mask = np.zeros((h, w), np.uint8)
    s0 = max(7, int(min(h, w) * 0.013))
    for i, (cx, cy, _v) in enumerate(peaks):
        size = s0 * (1.0 if i == 0 else 0.72)
        mask = cv2.bitwise_or(mask, _star_mask(h, w, cx, cy, size))

    mask = cv2.GaussianBlur(mask, (0, 0), 0.8)
    _, mask = cv2.threshold(mask, 40, 255, cv2.THRESH_BINARY)
    out = cv2.inpaint(img, mask, 2.6, cv2.INPAINT_TELEA)
    return out, mask, peaks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips_manual_exact")
    ap.add_argument("--output", default="work/story16/clips_manual_exact_v2")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/residual_pass_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)

    done = 0
    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        out, mask, peaks = process_image(img)
        cv2.imwrite(str(out_dir / p.name), out)

        h, w = img.shape[:2]
        ov = img.copy()
        for cx, cy, _ in peaks:
            cv2.circle(ov, (cx, cy), 3, (0, 0, 255), -1)
        x0, y0 = int(w * 0.84), int(h * 0.80)
        co = img[y0:h, x0:w]
        cv = ov[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        row = np.hstack([up(co), up(cv), up(cm), up(cn)])
        cv2.putText(
            row,
            f"{p.name} peaks={[(int(px), int(py)) for px, py, _ in peaks]}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(dbg_dir / p.name), row)
        done += 1

    print(f"done: {done}")
    print(f"out: {out_dir}")
    print(f"debug: {dbg_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
