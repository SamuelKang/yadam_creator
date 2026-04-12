#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def detect_peak(img: np.ndarray) -> tuple[int, int, float]:
    h, w = img.shape[:2]
    x0, y0 = int(w * 0.82), int(h * 0.82)
    roi = img[y0:h, x0:w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    wh = (hsv[:, :, 2].astype(np.float32) / 255.0) * (1.0 - hsv[:, :, 1].astype(np.float32) / 255.0)
    hp = np.clip(gray - cv2.GaussianBlur(gray, (0, 0), 1.8), 0, None) / 255.0
    score = wh * 0.95 + hp * 1.10
    # emphasize lower half of ROI
    yy, xx = np.mgrid[0 : score.shape[0], 0 : score.shape[1]]
    py = yy / max(1, score.shape[0] - 1)
    score = score * (0.65 + 0.7 * py)
    iy, ix = np.unravel_index(np.argmax(score), score.shape)
    return int(x0 + ix), int(y0 + iy), float(score[iy, ix])


def tiny_star_mask(h: int, w: int, cx: int, cy: int, s: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], np.int32)
    cv2.fillConvexPoly(m, pts, 255)
    cv2.ellipse(m, (cx, cy), (int(s * 1.5), max(1, int(s * 0.45))), 0, 0, 360, 255, -1)
    cv2.ellipse(m, (cx, cy), (max(1, int(s * 0.45)), int(s * 1.5)), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 0.7)
    _, m = cv2.threshold(m, 50, 255, cv2.THRESH_BINARY)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips_manual_exact_v2")
    ap.add_argument("--output", default="work/story16/clips_manual_exact_v3")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/finish_pass_debug")
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
        h, w = img.shape[:2]
        cx, cy, sc = detect_peak(img)

        s = max(5, int(min(h, w) * 0.0085))
        mask = tiny_star_mask(h, w, cx, cy, s)

        # Skip if peak confidence is too low (likely no residual mark).
        if sc < 0.20:
            out = img
            mask = np.zeros((h, w), np.uint8)
        else:
            out = cv2.inpaint(img, mask, 2.2, cv2.INPAINT_TELEA)

        cv2.imwrite(str(out_dir / p.name), out)

        x0, y0 = int(w * 0.84), int(h * 0.80)
        ov = img.copy()
        cv2.circle(ov, (cx, cy), 3, (0, 0, 255), -1)
        co = img[y0:h, x0:w]
        cv = ov[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        row = np.hstack([up(co), up(cv), up(cm), up(cn)])
        cv2.putText(row, f"{p.name} peak=({cx},{cy}) score={sc:.3f}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(dbg_dir / p.name), row)

        done += 1

    print(f"done: {done}")
    print(f"out: {out_dir}")
    print(f"debug: {dbg_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
