#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np


@dataclass
class MarkMeta:
    file: str
    w: int
    h: int
    cx: int
    cy: int
    x: int
    y: int
    bw: int
    bh: int
    area: int
    score: float
    mode: str


CENTER_HINTS = {
    (1408, 768): (0.9318, 0.9051),
    (2816, 1536): (0.9424, 0.9057),
    (1376, 768): (0.9418, 0.9051),
    (1024, 559): (0.9440, 0.9045),
    (2752, 1536): (0.9585, 0.8823),
    (912, 500): (0.9259, 0.9260),
    (2760, 1504): (0.9445, 0.9342),
}

NO_MARK_MANUAL = {
    "012.png",
    "014.png",
    "015.png",
    "021.png",
}

MANUAL_POINT_OVERRIDES = {
    "031.png": (1297, 711),
    "081.png": (2657, 1422),
    "096.png": (1329, 711),
    "113.png": (1329, 712),
    "116.png": (1329, 711),
    "118.png": (1329, 711),
    "156.png": (2628, 1410),
    "185.png": (983, 534),
    "186.png": (983, 534),
}


def expected_center(w: int, h: int) -> tuple[int, int]:
    hint = CENTER_HINTS.get((w, h))
    if hint:
        return int(round(w * hint[0])), int(round(h * hint[1]))
    return int(round(w * 0.94)), int(round(h * 0.905))


def detect_exact_mask(img: np.ndarray, file_name: str = "") -> tuple[np.ndarray, MarkMeta]:
    h, w = img.shape[:2]
    ex, ey = expected_center(w, h)
    mask_full = np.zeros((h, w), dtype=np.uint8)

    if file_name in NO_MARK_MANUAL:
        meta = MarkMeta(file_name, w, h, ex, ey, ex, ey, 0, 0, 0, 0.0, "no_mark_manual")
        return mask_full, meta

    if file_name in MANUAL_POINT_OVERRIDES:
        cx, cy = MANUAL_POINT_OVERRIDES[file_name]
        s = max(6, int(round(min(w, h) * 0.011)))
        pts = np.array([[cx, cy - s], [cx + s, cy], [cx, cy + s], [cx - s, cy]], dtype=np.int32)
        cv2.fillConvexPoly(mask_full, pts, 255)
        mask_full = cv2.dilate(mask_full, np.ones((3, 3), np.uint8), iterations=1)
        meta = MarkMeta(file_name, w, h, cx, cy, cx - s, cy - s, 2 * s, 2 * s, int(np.count_nonzero(mask_full)), 999.0, "manual_override")
        return mask_full, meta

    rx0 = max(0, int(w * 0.84))
    ry0 = max(0, int(h * 0.80))
    rx1 = w
    ry1 = h
    roi = img[ry0:ry1, rx0:rx1]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    blur = cv2.GaussianBlur(gray, (0, 0), 3.2)
    diff = gray.astype(np.int16) - blur.astype(np.int16)

    # bright + low saturation + local bright lift
    m1 = (hsv[:, :, 2] > 170) & (hsv[:, :, 1] < 85) & (diff > 6)
    m = (m1.astype(np.uint8) * 255)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    nlab, lab, stats, cents = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)

    best_i = -1
    best_score = -1e9
    for i in range(1, nlab):
        x, y, bw2, bh2, area = stats[i]
        if area < 10 or area > 2500:
            continue
        cx, cy = cents[i]
        gx, gy = rx0 + cx, ry0 + cy
        dist = ((gx - ex) ** 2 + (gy - ey) ** 2) ** 0.5

        comp = (lab == i)
        val_mean = float(hsv[:, :, 2][comp].mean())
        sat_mean = float(hsv[:, :, 1][comp].mean())

        # shape preference: neither too thin nor fully blobbed
        extent = float(area) / float(max(1, bw2 * bh2))
        extent_pen = abs(extent - 0.28)

        score = (
            area * 0.85
            + (val_mean - sat_mean * 0.5) * 1.8
            - dist * 2.8
            - extent_pen * 220.0
        )
        if score > best_score:
            best_score = score
            best_i = i

    if best_i == -1:
        # Relaxed per-frame local detection (still pixel-based, no fixed-shape fallback).
        lx0 = max(0, ex - int(w * 0.06))
        ly0 = max(0, ey - int(h * 0.08))
        lx1 = min(w, ex + int(w * 0.06))
        ly1 = min(h, ey + int(h * 0.08))
        lroi = img[ly0:ly1, lx0:lx1]
        lgray = cv2.cvtColor(lroi, cv2.COLOR_BGR2GRAY)
        lhsv = cv2.cvtColor(lroi, cv2.COLOR_BGR2HSV)
        lblur = cv2.GaussianBlur(lgray, (0, 0), 2.4)
        ldiff = lgray.astype(np.int16) - lblur.astype(np.int16)
        lm = ((lhsv[:, :, 2] > 150) & (lhsv[:, :, 1] < 100) & (ldiff > 2)).astype(np.uint8) * 255
        lm = cv2.morphologyEx(lm, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
        lm = cv2.morphologyEx(lm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
        n2, l2, s2, c2 = cv2.connectedComponentsWithStats((lm > 0).astype(np.uint8), 8)
        best2 = -1
        b2score = -1e9
        for i in range(1, n2):
            x, y, bw2, bh2, area = s2[i]
            if area < 6:
                continue
            cx, cy = c2[i]
            gx, gy = lx0 + cx, ly0 + cy
            dist = ((gx - ex) ** 2 + (gy - ey) ** 2) ** 0.5
            comp = (l2 == i)
            v = float(lhsv[:, :, 2][comp].mean())
            s = float(lhsv[:, :, 1][comp].mean())
            score2 = area * 1.4 + (v - 0.4 * s) * 1.5 - dist * 3.2
            if score2 > b2score:
                b2score = score2
                best2 = i

        if best2 != -1:
            comp = (l2 == best2).astype(np.uint8) * 255
            comp = cv2.dilate(comp, np.ones((2, 2), np.uint8), iterations=1)
            ys, xs = np.where(comp > 0)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            cx = int(round((x0 + x1) / 2.0))
            cy = int(round((y0 + y1) / 2.0))
            gx0, gy0 = lx0 + x0, ly0 + y0
            gcx, gcy = lx0 + cx, ly0 + cy
            mask_full[ly0:ly1, lx0:lx1] = comp
            meta = MarkMeta(
                file_name,
                w,
                h,
                gcx,
                gcy,
                gx0,
                gy0,
                int(x1 - x0 + 1),
                int(y1 - y0 + 1),
                int(np.count_nonzero(comp)),
                float(b2score),
                "exact_relaxed",
            )
            return mask_full, meta

        # If local signal is too weak, treat as no watermark and keep original untouched.
        sx0 = max(0, ex - int(w * 0.025))
        sy0 = max(0, ey - int(h * 0.035))
        sx1 = min(w, ex + int(w * 0.025))
        sy1 = min(h, ey + int(h * 0.035))
        sroi = img[sy0:sy1, sx0:sx1]
        if sroi.size > 0:
            sgray = cv2.cvtColor(sroi, cv2.COLOR_BGR2GRAY)
            sshsv = cv2.cvtColor(sroi, cv2.COLOR_BGR2HSV)
            sdiff = sgray.astype(np.int16) - cv2.GaussianBlur(sgray, (0, 0), 1.8).astype(np.int16)
            sig = float(np.mean((sshsv[:, :, 2] > 165) & (sshsv[:, :, 1] < 95) & (sdiff > 4)))
            if sig < 0.03:
                meta = MarkMeta(file_name, w, h, ex, ey, ex, ey, 0, 0, 0, float(best_score), "no_mark")
                return mask_full, meta

        # Last-resort tiny mask at expected center only if even relaxed local extraction fails.
        s = max(5, int(round(min(w, h) * 0.010)))
        pts = np.array([[ex, ey - s], [ex + s, ey], [ex, ey + s], [ex - s, ey]], dtype=np.int32)
        cv2.fillConvexPoly(mask_full, pts, 255)
        mask_full = cv2.dilate(mask_full, np.ones((3, 3), np.uint8), iterations=1)
        x0, y0 = max(0, ex - s), max(0, ey - s)
        bw2, bh2, area = 2 * s, 2 * s, int(np.count_nonzero(mask_full))
        meta = MarkMeta(file_name, w, h, ex, ey, x0, y0, bw2, bh2, area, float(best_score), "fallback")
        return mask_full, meta

    comp = (lab == best_i).astype(np.uint8) * 255
    # strengthen center and spikes a little
    comp = cv2.dilate(comp, np.ones((2, 2), np.uint8), iterations=1)
    comp = cv2.GaussianBlur(comp, (0, 0), 0.8)
    _, comp = cv2.threshold(comp, 60, 255, cv2.THRESH_BINARY)

    ys, xs = np.where(comp > 0)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    cx = int(round((x0 + x1) / 2.0))
    cy = int(round((y0 + y1) / 2.0))

    gx0, gy0 = rx0 + x0, ry0 + y0
    gcx, gcy = rx0 + cx, ry0 + cy

    mask_full[ry0:ry1, rx0:rx1] = comp

    meta = MarkMeta(
        file_name,
        w,
        h,
        gcx,
        gcy,
        gx0,
        gy0,
        int(x1 - x0 + 1),
        int(y1 - y0 + 1),
        int(np.count_nonzero(comp)),
        float(best_score),
        "exact",
    )
    return mask_full, meta


def restore(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    # 1) tiny inpaint pass on exact mask
    out = cv2.inpaint(img, mask, 1.8, cv2.INPAINT_TELEA)

    # 2) optional local alpha deblend against white to reduce residual sparkle
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return out
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    pad = 2
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(img.shape[1] - 1, x1 + pad)
    y1 = min(img.shape[0] - 1, y1 + pad)

    patch_i = img[y0 : y1 + 1, x0 : x1 + 1].astype(np.float32)
    patch_b = out[y0 : y1 + 1, x0 : x1 + 1].astype(np.float32)
    patch_m = (mask[y0 : y1 + 1, x0 : x1 + 1] > 0)[..., None]

    # alpha estimate per-pixel (white watermark model)
    denom = np.clip(255.0 - patch_b, 15.0, 255.0)
    a = np.clip((patch_i - patch_b) / denom, 0.0, 0.75)
    a = np.max(a, axis=2, keepdims=True)
    a = cv2.GaussianBlur(a, (0, 0), 0.7)
    if a.ndim == 2:
        a = a[:, :, None]

    # reverse blend: B = (I - a*255)/(1-a)
    restored = (patch_i - a * 255.0) / np.clip(1.0 - a, 0.25, 1.0)
    restored = np.clip(restored, 0, 255)

    merged = patch_b.copy()
    merged[patch_m[:, :, 0]] = restored[patch_m[:, :, 0]]
    out2 = out.copy()
    out2[y0 : y1 + 1, x0 : x1 + 1] = merged.astype(np.uint8)
    return out2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--output", default="work/story16/clips_manual_exact")
    ap.add_argument("--coords", default="work/story16/out/watermark_compare/manual_exact_coords.json")
    ap.add_argument("--debug-dir", default="work/story16/out/watermark_compare/manual_exact_debug")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)
    Path(args.coords).parent.mkdir(parents=True, exist_ok=True)

    metas: list[MarkMeta] = []

    for p in sorted(in_dir.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue

        mask, meta = detect_exact_mask(img, p.name)

        out = restore(img, mask)
        cv2.imwrite(str(out_dir / p.name), out)

        # Save debug overlay for strict per-frame coordinate traceability.
        ov = img.copy()
        ys, xs = np.where(mask > 0)
        if len(xs) > 0:
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
            cv2.rectangle(ov, (x0, y0), (x1, y1), (0, 255, 0), 1)
            cv2.circle(ov, (meta.cx, meta.cy), 3, (0, 0, 255), -1)
            tint = ov.copy()
            tint[mask > 0] = (0, 255, 255)
            ov = cv2.addWeighted(tint, 0.25, ov, 0.75, 0)

        h, w = img.shape[:2]
        rx0, ry0 = int(w * 0.84), int(h * 0.80)
        crop_o = img[ry0:h, rx0:w]
        crop_v = ov[ry0:h, rx0:w]
        crop_n = out[ry0:h, rx0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        row = np.hstack([up(crop_o), up(crop_v), up(crop_n)])
        cv2.putText(
            row,
            f"{p.name} mode={meta.mode} score={meta.score:.1f} center=({meta.cx},{meta.cy})",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(dbg_dir / p.name), row)

        metas.append(meta)

    Path(args.coords).write_text(json.dumps([asdict(m) for m in metas], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {len(metas)}")
    print(f"out: {out_dir}")
    print(f"coords: {args.coords}")
    print(f"debug: {dbg_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
