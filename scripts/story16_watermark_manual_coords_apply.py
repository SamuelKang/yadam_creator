#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class CoordRow:
    file: str
    w: int
    h: int
    cx: int
    cy: int
    score_template: float
    score_peak: float
    method: str


def synth_star_template(sz: int = 43) -> np.ndarray:
    c = sz // 2
    t = np.zeros((sz, sz), np.float32)
    for y in range(sz):
        for x in range(sz):
            dx = abs(x - c) / (sz * 0.5)
            dy = abs(y - c) / (sz * 0.5)
            diamond = max(0.0, 1.0 - (dx + dy) * 1.25)
            hsp = max(0.0, 1.0 - (dx * 1.8 + dy * 0.38))
            vsp = max(0.0, 1.0 - (dy * 1.8 + dx * 0.38))
            t[y, x] = max(diamond, hsp * 0.85, vsp * 0.85)
    t = cv2.GaussianBlur(t, (0, 0), 1.1)
    t /= float(t.max() + 1e-6)
    return t


def detect_by_template(img: np.ndarray, tmpl_base: np.ndarray) -> tuple[int, int, float, int]:
    h, w = img.shape[:2]
    x0, y0 = int(w * 0.82), int(h * 0.80)
    roi = img[y0:h, x0:w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    wh = (hsv[:, :, 2].astype(np.float32) / 255.0) * (1.0 - hsv[:, :, 1].astype(np.float32) / 255.0)
    hp = np.clip(gray - cv2.GaussianBlur(gray, (0, 0), 2.0), 0, None) / 255.0
    feat = np.clip(wh * 0.85 + hp * 1.20, 0.0, 1.0)

    scale = max(0.72, min(1.70, min(h / 768.0, w / 1376.0) * 1.02))
    ts = max(19, int(round(tmpl_base.shape[0] * scale)))
    tmpl = cv2.resize(tmpl_base, (ts, ts), interpolation=cv2.INTER_CUBIC)

    res = cv2.matchTemplate(feat, tmpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    cx = x0 + loc[0] + ts // 2
    cy = y0 + loc[1] + ts // 2
    return int(cx), int(cy), float(mx), int(ts)


def detect_by_peak(img: np.ndarray) -> tuple[int, int, float]:
    h, w = img.shape[:2]
    x0, y0 = int(w * 0.82), int(h * 0.80)
    roi = img[y0:h, x0:w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    wh = (hsv[:, :, 2].astype(np.float32) / 255.0) * (1.0 - hsv[:, :, 1].astype(np.float32) / 255.0)
    hp = np.clip(gray - cv2.GaussianBlur(gray, (0, 0), 1.9), 0, None) / 255.0
    score = wh * 0.95 + hp * 1.05

    yy, xx = np.mgrid[0 : score.shape[0], 0 : score.shape[1]]
    py = yy / max(1, score.shape[0] - 1)
    px = xx / max(1, score.shape[1] - 1)
    score = score * (0.68 + 0.55 * py) + px * 0.03

    iy, ix = np.unravel_index(np.argmax(score), score.shape)
    return int(x0 + ix), int(y0 + iy), float(score[iy, ix])


def choose_coord(img: np.ndarray, tmpl_base: np.ndarray) -> tuple[int, int, float, float, str, int]:
    cxt, cyt, st, ts = detect_by_template(img, tmpl_base)
    cxp, cyp, sp = detect_by_peak(img)

    if st >= 0.52:
        cx = int(round(cxt * 0.80 + cxp * 0.20))
        cy = int(round(cyt * 0.80 + cyp * 0.20))
        method = "template_high"
    elif st >= 0.30:
        cx = int(round(cxt * 0.60 + cxp * 0.40))
        cy = int(round(cyt * 0.60 + cyp * 0.40))
        method = "template_mid"
    else:
        cx, cy = cxp, cyp
        method = "peak_only"

    return cx, cy, st, sp, method, ts


def star_mask(h: int, w: int, cx: int, cy: int, ts: int, aggressive: bool = False) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    s = max(8, int(ts * (0.34 if aggressive else 0.28)))
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], np.int32)
    cv2.fillConvexPoly(m, pts, 255)
    cv2.ellipse(m, (cx, cy), (int(s * (2.0 if aggressive else 1.75)), max(1, int(s * 0.58))), 0, 0, 360, 255, -1)
    cv2.ellipse(m, (cx, cy), (max(1, int(s * 0.58)), int(s * (2.0 if aggressive else 1.75))), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 0.9)
    _, m = cv2.threshold(m, 42, 255, cv2.THRESH_BINARY)
    return m


def remove_with_coord(img: np.ndarray, cx: int, cy: int, ts: int, st: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = img.shape[:2]
    m1 = star_mask(h, w, cx, cy, ts, aggressive=(st < 0.33))
    out = cv2.inpaint(img, m1, 2.8, cv2.INPAINT_TELEA)

    # tiny finishing pass at same center for residual sparkle core
    m2 = star_mask(h, w, cx, cy, max(14, int(ts * 0.65)), aggressive=False)
    out2 = cv2.inpaint(out, m2, 1.9, cv2.INPAINT_TELEA)

    mask = cv2.bitwise_or(m1, m2)
    return out2, mask


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--output", default="work/story16/clips_manual_coords")
    ap.add_argument("--coords", default="work/story16/out/watermark_compare/manual_coords.json")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/manual_coords_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    debug_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    Path(args.coords).parent.mkdir(parents=True, exist_ok=True)

    tmpl_base = synth_star_template(43)

    rows: list[CoordRow] = []
    done = 0
    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        cx, cy, st, sp, method, ts = choose_coord(img, tmpl_base)

        out, mask = remove_with_coord(img, cx, cy, ts, st)
        cv2.imwrite(str(out_dir / p.name), out)

        rows.append(CoordRow(p.name, w, h, cx, cy, st, sp, method))

        x0, y0 = int(w * 0.84), int(h * 0.80)
        ov = img.copy()
        cv2.circle(ov, (cx, cy), 3, (0, 0, 255), -1)
        co = img[y0:h, x0:w]
        cv = ov[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        row = np.hstack([up(co), up(cv), up(cm), up(cn)])
        cv2.putText(
            row,
            f"{p.name} method={method} st={st:.3f} sp={sp:.3f} c=({cx},{cy})",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(debug_dir / p.name), row)
        done += 1

    Path(args.coords).write_text(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {done}")
    print(f"out: {out_dir}")
    print(f"coords: {args.coords}")
    print(f"debug: {debug_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
