from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

from PIL import Image, ImageDraw, ImageOps


def _parse_scene_ids(values: Iterable[str]) -> List[int]:
    out: List[int] = []
    for raw in values:
        for part in str(raw).split(","):
            token = part.strip()
            if not token:
                continue
            if "-" in token:
                a, b = token.split("-", 1)
                start = int(a)
                end = int(b)
                step = 1 if end >= start else -1
                out.extend(range(start, end + step, step))
            else:
                out.append(int(token))

    seen = set()
    uniq: List[int] = []
    for sid in out:
        if sid in seen:
            continue
        seen.add(sid)
        uniq.append(sid)
    return uniq


def _label_tile(img: Image.Image, label: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 108, 26), fill=(0, 0, 0))
    draw.text((8, 6), label, fill=(255, 255, 255))
    return img


def build_contact_sheet(
    story_id: str,
    scene_ids: List[int],
    thumb_width: int,
    columns: int,
    jpeg_quality: int,
) -> Path:
    clips_dir = Path("work") / story_id / "clips"
    out_dir = Path("work") / story_id / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{story_id}_clips_{scene_ids[0]:03d}_{scene_ids[-1]:03d}_sheet.jpg"

    thumb_height = max(1, int(round(thumb_width * 9 / 16)))
    tile_height = thumb_height + 30
    tiles: List[Image.Image] = []

    for sid in scene_ids:
        clip_path = clips_dir / f"{sid:03d}.jpg"
        if not clip_path.exists():
            raise FileNotFoundError(f"missing clip: {clip_path}")
        with Image.open(clip_path) as im:
            frame = ImageOps.fit(im.convert("RGB"), (thumb_width, thumb_height), method=Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (thumb_width, tile_height), color=(248, 244, 236))
        tile.paste(frame, (0, 30))
        tiles.append(_label_tile(tile, f"scene {sid:03d}"))

    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_width, rows * tile_height), color=(230, 225, 214))
    for idx, tile in enumerate(tiles):
        x = (idx % columns) * thumb_width
        y = (idx // columns) * tile_height
        sheet.paste(tile, (x, y))

    sheet.save(out_path, format="JPEG", quality=jpeg_quality, optimize=True)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a lightweight contact sheet for clip continuity review.")
    parser.add_argument("--story-id", required=True, help="Story id, e.g. story25")
    parser.add_argument("--scenes", nargs="+", required=True, help="Scene ids or ranges, e.g. 112-118 or 112 113")
    parser.add_argument("--thumb-width", type=int, default=320, help="Thumbnail width in pixels")
    parser.add_argument("--columns", type=int, default=3, help="Number of columns in the sheet")
    parser.add_argument("--jpeg-quality", type=int, default=70, help="Output JPEG quality")
    args = parser.parse_args()

    scene_ids = _parse_scene_ids(args.scenes)
    if not scene_ids:
        raise SystemExit("no scene ids provided")

    out_path = build_contact_sheet(
        story_id=args.story_id,
        scene_ids=scene_ids,
        thumb_width=args.thumb_width,
        columns=max(1, args.columns),
        jpeg_quality=max(30, min(95, args.jpeg_quality)),
    )
    print(out_path)


if __name__ == "__main__":
    main()
