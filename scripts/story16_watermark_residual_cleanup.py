#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def detect_components(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0 = int(w * 0.82), int(h * 0.80)
    roi = img[y0:h, x0:w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp = np.clip(gray - cv2.GaussianBlur(gray, (0, 0), 1.8), 0, None)

    cand = ((hsv[:, :, 2] > 145) & (hsv[:, :, 1] < 105) & (hp > 5.5)).astype(np.uint8) * 255
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    n, lab, stats, cents = cv2.connectedComponentsWithStats((cand > 0).astype(np.uint8), 8)
    keep = np.zeros_like(cand)

    ex, ey = int(w * 0.94), int(h * 0.905)
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < 10 or area > 2600:
            continue
        extent = area / max(1, ww * hh)
        if extent < 0.10 or extent > 0.82:
            continue
        cx, cy = cents[i]
        gx, gy = x0 + cx, y0 + cy
        dist = ((gx - ex) ** 2 + (gy - ey) ** 2) ** 0.5
        if dist > max(180, 0.20 * max(w, h)):
            continue
        keep[lab == i] = 255

    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8), iterations=1)
    mask = np.zeros((h, w), np.uint8)
    mask[y0:h, x0:w] = keep
    return mask


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips_manual_clicked")
    ap.add_argument("--output", default="work/story16/clips_manual_clicked_clean")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/residual_cleanup_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg.mkdir(parents=True, exist_ok=True)

    done = 0
    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        mask = detect_components(img)
        if np.count_nonzero(mask) > 0:
            out = cv2.inpaint(img, mask, 2.4, cv2.INPAINT_TELEA)
        else:
            out = img

        cv2.imwrite(str(out_dir / p.name), out)

        h, w = img.shape[:2]
        x0, y0 = int(w * 0.84), int(h * 0.80)
        co = img[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        tile = np.hstack([up(co), up(cm), up(cn)])
        cv2.putText(tile, f"{p.name} nz={int(np.count_nonzero(mask))}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(dbg / p.name), tile)
        done += 1

    print(f"done: {done}")
    print(f"out: {out_dir}")
    print(f"debug: {dbg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
