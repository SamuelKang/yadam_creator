#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import cv2
import numpy as np


@dataclass
class DetectResult:
    score: float
    x: int
    y: int
    tw: int
    th: int
    cx: int
    cy: int


# Resolution-specific median centers measured from story16 clips.
CENTER_HINTS = {
    (1408, 768): (0.9318, 0.9051),
    (2816, 1536): (0.9424, 0.9057),
    (1376, 768): (0.9418, 0.9051),
    (1024, 559): (0.9440, 0.9045),
    (2752, 1536): (0.9585, 0.8823),
    (912, 500): (0.9259, 0.9260),
    (2760, 1504): (0.9445, 0.9342),
}


def load_template(src_dir: Path) -> np.ndarray:
    base = cv2.imread(str(src_dir / "020.png"), cv2.IMREAD_COLOR)
    if base is None:
        raise RuntimeError("cannot read template source image: 020.png")
    h, w = base.shape[:2]
    return base[int(h * 0.852) : int(h * 0.955), int(w * 0.905) : int(w * 0.975)]


def detect_mark(img: np.ndarray, tmpl_base: np.ndarray, base_wh=(1376, 768)) -> DetectResult:
    h, w = img.shape[:2]
    bw, bh = base_wh
    tw = max(8, int(round(tmpl_base.shape[1] * w / bw)))
    th = max(8, int(round(tmpl_base.shape[0] * h / bh)))
    tmpl = cv2.resize(tmpl_base, (tw, th), interpolation=cv2.INTER_CUBIC)

    sx0, sy0 = int(w * 0.84), int(h * 0.80)
    search = img[sy0:h, sx0:w]
    res = cv2.matchTemplate(
        cv2.cvtColor(search, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY),
        cv2.TM_CCOEFF_NORMED,
    )
    _, mx, _, loc = cv2.minMaxLoc(res)
    x = sx0 + loc[0]
    y = sy0 + loc[1]

    # mark center from matched template region
    cx = int(round(x + tw * 0.53))
    cy = int(round(y + th * 0.52))

    # blend with resolution hint for stability
    hint = CENTER_HINTS.get((w, h))
    if hint is not None:
        hx = int(round(w * hint[0]))
        hy = int(round(h * hint[1]))
        # lower-confidence matches rely more on hint
        if mx < 0.25:
            a = 0.25
        elif mx < 0.45:
            a = 0.55
        else:
            a = 0.75
        cx = int(round(cx * a + hx * (1.0 - a)))
        cy = int(round(cy * a + hy * (1.0 - a)))

    return DetectResult(float(mx), x, y, tw, th, cx, cy)


def build_masks(shape: tuple[int, int], cx: int, cy: int, scale: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, w = shape
    # tight rect around core sparkle
    rw = max(8, int(round(w * 0.018)))
    rh = max(8, int(round(h * 0.030)))
    x0 = max(0, cx - rw // 2)
    y0 = max(0, cy - rh // 2)
    x1 = min(w, x0 + rw)
    y1 = min(h, y0 + rh)

    rect = np.zeros((h, w), dtype=np.uint8)
    rect[y0:y1, x0:x1] = 255

    # diamond mask for star center
    s = max(6, int(round(scale * 0.014)))
    dia = np.zeros((h, w), dtype=np.uint8)
    pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], dtype=np.int32)
    cv2.fillConvexPoly(dia, pts, 255)
    dia = cv2.dilate(dia, np.ones((3, 3), np.uint8), iterations=1)

    # combined mask
    combo = cv2.bitwise_or(rect, dia)
    return rect, dia, combo


def local_quality(out: np.ndarray, tmpl_base: np.ndarray, det: DetectResult) -> float:
    h, w = out.shape[:2]
    tw, th = det.tw, det.th
    x = max(0, min(w - tw, det.x))
    y = max(0, min(h - th, det.y))

    # residual template correlation near predicted area (lower is better)
    patch = out[y : y + th, x : x + tw]
    tmpl = cv2.resize(tmpl_base, (tw, th), interpolation=cv2.INTER_CUBIC)
    g1 = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g1 -= g1.mean()
    g2 -= g2.mean()
    denom = (np.linalg.norm(g1) * np.linalg.norm(g2) + 1e-6)
    corr = float(np.sum(g1 * g2) / denom)

    # artifact penalty: sudden gradient energy in a small neighborhood
    rx0 = max(0, det.cx - int(0.035 * w))
    ry0 = max(0, det.cy - int(0.050 * h))
    rx1 = min(w, det.cx + int(0.035 * w))
    ry1 = min(h, det.cy + int(0.050 * h))
    roi = cv2.cvtColor(out[ry0:ry1, rx0:rx1], cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(roi, cv2.CV_32F, 0, 1, ksize=3)
    grad = float(np.mean(np.sqrt(gx * gx + gy * gy)))

    return corr * 1.0 + grad * 0.0012


def process_one(img: np.ndarray, tmpl_base: np.ndarray) -> tuple[np.ndarray, DetectResult, str]:
    det = detect_mark(img, tmpl_base)
    h, w = img.shape[:2]
    scale = min(h, w)

    center_candidates: list[tuple[int, int, str]] = []
    center_candidates.append((det.cx, det.cy, "m0"))
    # Low-confidence detection: trust hint center additionally.
    hint = CENTER_HINTS.get((w, h))
    if hint is not None and det.score < 0.45:
        center_candidates.append((int(round(w * hint[0])), int(round(h * hint[1])), "h0"))

    step = max(2, int(round(min(w, h) * 0.004)))
    expanded: list[tuple[int, int, str]] = []
    for cx, cy, tag in center_candidates:
        expanded.append((cx, cy, tag))
        expanded.append((cx - step, cy, tag + "L"))
        expanded.append((cx + step, cy, tag + "R"))
        expanded.append((cx, cy - step, tag + "U"))
        expanded.append((cx, cy + step, tag + "D"))

    best_name = ""
    best_img = img
    best_q = 1e9
    seen = set()
    for cx, cy, ctag in expanded:
        cx = int(max(0, min(w - 1, cx)))
        cy = int(max(0, min(h - 1, cy)))
        if (cx, cy) in seen:
            continue
        seen.add((cx, cy))
        rect, _, combo = build_masks((h, w), cx, cy, scale)
        # Only use telea variants; NS gave more blur artifacts for this watermark.
        cand_variants = [
            (f"telea_rect_{ctag}", cv2.inpaint(img, rect, 2.0, cv2.INPAINT_TELEA)),
            (f"telea_combo_{ctag}", cv2.inpaint(img, combo, 2.2, cv2.INPAINT_TELEA)),
        ]
        for name, cand in cand_variants:
            det2 = DetectResult(det.score, det.x, det.y, det.tw, det.th, cx, cy)
            q = local_quality(cand, tmpl_base, det2)
            if q < best_q:
                best_q = q
                best_name = name
                best_img = cand

    return best_img, det, best_name


def main() -> int:
    ap = argparse.ArgumentParser(description="Story16 watermark manual-tuned pass")
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--output", default="work/story16/clips_manual_tuned")
    ap.add_argument("--report", default="work/story16/out/watermark_compare/manual_tuned_report.txt")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)

    tmpl_base = load_template(in_dir)

    lines = []
    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        out, det, chosen = process_one(img, tmpl_base)
        dst = out_dir / p.name
        cv2.imwrite(str(dst), out)
        lines.append(
            f"{p.name}\tscore={det.score:.3f}\tcx={det.cx}\tcy={det.cy}\tmethod={chosen}"
        )

    Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done: {len(lines)} images")
    print(f"out: {out_dir}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
