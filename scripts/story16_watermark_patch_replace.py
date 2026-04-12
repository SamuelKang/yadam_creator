#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path

import cv2
import numpy as np


def border_mismatch(img: np.ndarray, tx: int, ty: int, tw: int, th: int, sx: int, sy: int) -> float:
    src = img[sy : sy + th, sx : sx + tw]
    score = 0.0
    n = 0
    if ty - 1 >= 0:
        score += float(np.mean(np.abs(src[0].astype(np.float32) - img[ty - 1, tx : tx + tw].astype(np.float32))))
        n += 1
    if ty + th < img.shape[0]:
        score += float(np.mean(np.abs(src[-1].astype(np.float32) - img[ty + th, tx : tx + tw].astype(np.float32))))
        n += 1
    if tx - 1 >= 0:
        score += float(np.mean(np.abs(src[:, 0].astype(np.float32) - img[ty : ty + th, tx - 1].astype(np.float32))))
        n += 1
    if tx + tw < img.shape[1]:
        score += float(np.mean(np.abs(src[:, -1].astype(np.float32) - img[ty : ty + th, tx + tw].astype(np.float32))))
        n += 1
    return score / max(1, n)


def replace_patch(img: np.ndarray, cx: int, cy: int) -> tuple[np.ndarray, np.ndarray]:
    h, w = img.shape[:2]
    tw = max(22, int(min(h, w) * 0.05))
    th = tw
    tx = max(0, min(w - tw, cx - tw // 2))
    ty = max(0, min(h - th, cy - th // 2))

    gap = max(8, tw // 3)
    candidates = []
    # left / upper-left / up / right-up fallback
    for sx, sy in [
        (tx - tw - gap, ty),
        (tx - tw - gap, ty - th // 2),
        (tx, ty - th - gap),
        (tx - tw // 2, ty - th - gap),
        (tx + tw + gap, ty),
    ]:
        if sx < 0 or sy < 0 or sx + tw > w or sy + th > h:
            continue
        candidates.append((sx, sy))

    if not candidates:
        # fallback: heavy inpaint on square
        mask = np.zeros((h, w), np.uint8)
        mask[ty : ty + th, tx : tx + tw] = 255
        out = cv2.inpaint(img, mask, 3.2, cv2.INPAINT_TELEA)
        return out, mask

    best = None
    best_s = 1e9
    for sx, sy in candidates:
        s = border_mismatch(img, tx, ty, tw, th, sx, sy)
        if s < best_s:
            best_s = s
            best = (sx, sy)

    sx, sy = best
    patch = img[sy : sy + th, sx : sx + tw].copy()
    mask = np.full((th, tw), 255, np.uint8)
    center = (tx + tw // 2, ty + th // 2)
    out = cv2.seamlessClone(patch, img, mask, center, cv2.NORMAL_CLONE)

    # light cleanup to avoid clone seams
    full_mask = np.zeros((h, w), np.uint8)
    full_mask[ty : ty + th, tx : tx + tw] = 255
    out = cv2.inpaint(out, full_mask, 1.2, cv2.INPAINT_TELEA)
    return out, full_mask


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='work/story16/clips')
    ap.add_argument('--coords', default='work/story16/out/watermark_compare/manual_coords_clicked.json')
    ap.add_argument('--output', default='work/story16/clips_manual_patch')
    ap.add_argument('--debug-dir', default='work/story16/out/watermark_compare/manual_patch_debug')
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    dbg_dir = Path(args.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)

    rows = {r['file']: r for r in json.loads(Path(args.coords).read_text(encoding='utf-8'))}

    done = 0
    for p in sorted(in_dir.glob('*.png')):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        r = rows.get(p.name)
        if not r:
            cv2.imwrite(str(out_dir / p.name), img)
            continue

        cx, cy = int(r['cx']), int(r['cy'])
        out, mask = replace_patch(img, cx, cy)
        cv2.imwrite(str(out_dir / p.name), out)

        h, w = img.shape[:2]
        x0, y0 = int(w * 0.84), int(h * 0.80)
        co = img[y0:h, x0:w]
        cm = cv2.cvtColor(mask[y0:h, x0:w], cv2.COLOR_GRAY2BGR)
        cn = out[y0:h, x0:w]
        up = lambda a: cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        tile = np.hstack([up(co), up(cm), up(cn)])
        cv2.putText(tile, f"{p.name} c=({cx},{cy})", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(dbg_dir / p.name), tile)
        done += 1

    print(f"done: {done}")
    print(f"out: {out_dir}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
