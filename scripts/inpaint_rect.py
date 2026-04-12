#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


Rect = Tuple[int, int, int, int]  # x, y, w, h
RectBRFrac = Tuple[float, float, float, float]  # w_frac, h_frac, margin_right_frac, margin_bottom_frac


def parse_rect(text: str) -> Rect:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid rect '{text}', expected x,y,w,h")
    x, y, w, h = (int(v) for v in parts)
    if w <= 0 or h <= 0:
        raise ValueError(f"invalid rect '{text}', w/h must be > 0")
    return (x, y, w, h)


def load_rects(args_rect: Sequence[str], rect_file: str | None) -> List[Rect]:
    rects: List[Rect] = []
    for raw in args_rect:
        rects.append(parse_rect(raw))
    if rect_file:
        data = json.loads(Path(rect_file).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("--rect-file must be a JSON list")
        for row in data:
            if isinstance(row, str):
                rects.append(parse_rect(row))
                continue
            if not isinstance(row, dict):
                raise ValueError("rect-file entries must be string or object")
            x = int(row["x"])
            y = int(row["y"])
            w = int(row["w"])
            h = int(row["h"])
            rects.append((x, y, w, h))
    if not rects:
        raise ValueError("no rects provided; use --rect or --rect-file")
    return rects


def parse_rect_br_frac(text: str) -> RectBRFrac:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid --rect-br '{text}', expected w_frac,h_frac,margin_right_frac,margin_bottom_frac")
    wf, hf, mrf, mbf = (float(v) for v in parts)
    for v in (wf, hf, mrf, mbf):
        if v < 0 or v >= 1:
            raise ValueError(f"invalid --rect-br '{text}', all values must be >=0 and <1")
    if wf <= 0 or hf <= 0:
        raise ValueError(f"invalid --rect-br '{text}', width/height fraction must be >0")
    if wf + mrf >= 1 or hf + mbf >= 1:
        raise ValueError(f"invalid --rect-br '{text}', rect exceeds image bounds")
    return (wf, hf, mrf, mbf)


def rects_from_br_frac(width: int, height: int, specs: Sequence[RectBRFrac]) -> List[Rect]:
    out: List[Rect] = []
    for wf, hf, mrf, mbf in specs:
        rw = max(1, int(round(width * wf)))
        rh = max(1, int(round(height * hf)))
        mr = int(round(width * mrf))
        mb = int(round(height * mbf))
        x = max(0, width - mr - rw)
        y = max(0, height - mb - rh)
        out.append((x, y, rw, rh))
    return out


def iter_images(input_path: Path, pattern: str) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    for p in sorted(input_path.glob(pattern)):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def inpaint_with_cv2(
    src_path: Path,
    dst_path: Path,
    rects: Sequence[Rect],
    expand: int,
    radius: float,
    method: str,
) -> None:
    import cv2  # type: ignore
    import numpy as np

    img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"failed to read image: {src_path}")
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    for x, y, rw, rh in rects:
        x0 = max(0, x - expand)
        y0 = max(0, y - expand)
        x1 = min(w, x + rw + expand)
        y1 = min(h, y + rh + expand)
        mask[y0:y1, x0:x1] = 255

    cv_method = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    out = cv2.inpaint(img, mask, inpaintRadius=radius, flags=cv_method)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dst_path), out)
    if not ok:
        raise RuntimeError(f"failed to write image: {dst_path}")


def _border_mismatch_score(img, x: int, y: int, w: int, h: int, sx: int, sy: int) -> float:
    import numpy as np

    src = img[sy : sy + h, sx : sx + w]
    score = 0.0
    n = 0
    # Compare source patch borders with target-neighbor pixels around insertion region.
    if y - 1 >= 0:
        score += float(np.mean(np.abs(src[0, :, :].astype(np.float32) - img[y - 1, x : x + w, :].astype(np.float32))))
        n += 1
    if y + h < img.shape[0]:
        score += float(np.mean(np.abs(src[-1, :, :].astype(np.float32) - img[y + h, x : x + w, :].astype(np.float32))))
        n += 1
    if x - 1 >= 0:
        score += float(np.mean(np.abs(src[:, 0, :].astype(np.float32) - img[y : y + h, x - 1, :].astype(np.float32))))
        n += 1
    if x + w < img.shape[1]:
        score += float(np.mean(np.abs(src[:, -1, :].astype(np.float32) - img[y : y + h, x + w, :].astype(np.float32))))
        n += 1
    return score / max(1, n)


def patch_blend_with_cv2(src_path: Path, dst_path: Path, rects: Sequence[Rect], expand: int = 0) -> None:
    import cv2  # type: ignore
    import numpy as np

    img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"failed to read image: {src_path}")
    H, W = img.shape[:2]
    out = img.copy()

    for x, y, rw, rh in rects:
        x0 = max(0, x - expand)
        y0 = max(0, y - expand)
        x1 = min(W, x + rw + expand)
        y1 = min(H, y + rh + expand)
        w = x1 - x0
        h = y1 - y0
        if w <= 2 or h <= 2:
            continue

        candidates = []
        # left
        if x0 - w >= 0:
            candidates.append((x0 - w, y0))
        # top
        if y0 - h >= 0:
            candidates.append((x0, y0 - h))
        # top-left
        if x0 - w >= 0 and y0 - h >= 0:
            candidates.append((x0 - w, y0 - h))
        # left-shifted partial fallback
        if x0 - max(8, w // 2) >= 0:
            candidates.append((x0 - max(8, w // 2), y0))

        if not candidates:
            # If no patch source available (extreme edge case), keep current region for later inpaint fallback.
            continue

        best = None
        best_score = None
        for sx, sy in candidates:
            if sx < 0 or sy < 0 or sx + w > W or sy + h > H:
                continue
            score = _border_mismatch_score(out, x0, y0, w, h, sx, sy)
            if best_score is None or score < best_score:
                best_score = score
                best = (sx, sy)
        if best is None:
            continue

        sx, sy = best
        patch = out[sy : sy + h, sx : sx + w].copy()
        mask = np.full((h, w), 255, dtype=np.uint8)
        center = (x0 + w // 2, y0 + h // 2)
        out = cv2.seamlessClone(patch, out, mask, center, cv2.NORMAL_CLONE)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dst_path), out)
    if not ok:
        raise RuntimeError(f"failed to write image: {dst_path}")


def inpaint_with_pillow(src_path: Path, dst_path: Path, rects: Sequence[Rect], feather: int = 8) -> None:
    # Lightweight fallback when OpenCV is unavailable.
    from PIL import Image, ImageFilter

    im = Image.open(src_path).convert("RGB")
    out = im.copy()
    width, height = out.size

    for x, y, rw, rh in rects:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(width, x + rw)
        y1 = min(height, y + rh)
        if x1 <= x0 or y1 <= y0:
            continue
        patch_w = x1 - x0
        patch_h = y1 - y0

        # Sample from above first; if not enough space, sample below.
        src_top = y0 - patch_h
        src_bottom = y1 + patch_h
        if src_top >= 0:
            sample_box = (x0, src_top, x1, y0)
        elif src_bottom <= height:
            sample_box = (x0, y1, x1, src_bottom)
        else:
            # Last fallback: use nearest available strip and resize.
            strip_h = max(1, min(patch_h, y0 if y0 > 0 else height - y1))
            if y0 > 0:
                sample_box = (x0, y0 - strip_h, x1, y0)
            else:
                sample_box = (x0, y1, x1, y1 + strip_h)

        sample = out.crop(sample_box).resize((patch_w, patch_h), Image.Resampling.BICUBIC)
        blurred = sample.filter(ImageFilter.GaussianBlur(radius=max(1, feather / 2)))
        out.paste(blurred, (x0, y0))

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_path)


def build_output_path(src: Path, out: Path | None, input_root: Path) -> Path:
    if out is None:
        return src.with_name(f"{src.stem}_inpaint{src.suffix}")
    if out.is_file():
        return out
    if out.suffix:
        return out
    if input_root.is_file():
        return out / src.name
    rel = src.relative_to(input_root)
    return out / rel


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generic rectangular-region background restoration using OpenCV inpainting (with Pillow fallback)."
    )
    ap.add_argument("--input", required=True, help="input image file or directory")
    ap.add_argument("--output", default=None, help="output file or directory (default: *_inpaint beside source)")
    ap.add_argument("--glob", default="**/*", help="glob when --input is a directory (default: **/*)")
    ap.add_argument("--rect", action="append", default=[], help="rectangle x,y,w,h (can repeat)")
    ap.add_argument("--rect-file", default=None, help="JSON list of rects, e.g. [{\"x\":10,\"y\":20,\"w\":120,\"h\":50}]")
    ap.add_argument(
        "--rect-br",
        action="append",
        default=[],
        help="relative bottom-right rect w_frac,h_frac,margin_right_frac,margin_bottom_frac (can repeat)",
    )
    ap.add_argument("--expand", type=int, default=2, help="expand each rect by N pixels for mask context")
    ap.add_argument("--radius", type=float, default=3.0, help="OpenCV inpaint radius")
    ap.add_argument("--method", choices=["telea", "ns"], default="telea", help="OpenCV inpaint method")
    ap.add_argument("--mode", choices=["inpaint", "patch"], default="inpaint", help="restoration mode")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    output_path = Path(args.output) if args.output else None

    rects_fixed = load_rects(args.rect, args.rect_file) if (args.rect or args.rect_file) else []
    rects_br_specs = [parse_rect_br_frac(v) for v in (args.rect_br or [])]
    if not rects_fixed and not rects_br_specs:
        raise SystemExit("no rects provided; use --rect/--rect-file and/or --rect-br")
    images = list(iter_images(input_path, args.glob))
    if not images:
        raise SystemExit("no images matched input")

    use_cv2 = True
    try:
        import cv2  # noqa: F401
    except Exception:
        use_cv2 = False

    done = 0
    for src in images:
        dst = build_output_path(src, output_path, input_path)
        # Build per-image rect set (fixed + relative bottom-right).
        rects = list(rects_fixed)
        if rects_br_specs:
            from PIL import Image

            with Image.open(src) as im:
                w, h = im.size
            rects.extend(rects_from_br_frac(w, h, rects_br_specs))
        if use_cv2 and args.mode == "patch":
            patch_blend_with_cv2(
                src_path=src,
                dst_path=dst,
                rects=rects,
                expand=max(0, int(args.expand)),
            )
        elif use_cv2:
            inpaint_with_cv2(
                src_path=src,
                dst_path=dst,
                rects=rects,
                expand=max(0, int(args.expand)),
                radius=float(args.radius),
                method=str(args.method),
            )
        else:
            inpaint_with_pillow(src_path=src, dst_path=dst, rects=rects, feather=8)
        done += 1
        print(f"[ok] {src} -> {dst}")

    print(f"done: {done} image(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
