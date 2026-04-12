#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def load_coords(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for row in data:
        out[row["file"]] = row
    return out


def save_coords(path: Path, rows: dict[str, dict]) -> None:
    arr = [rows[k] for k in sorted(rows.keys())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Manual click labeler for story16 watermark centers")
    ap.add_argument("--input", default="work/story16/clips")
    ap.add_argument("--coords", default="work/story16/out/watermark_compare/manual_coords_clicked.json")
    ap.add_argument("--start", default="001.png")
    args = ap.parse_args()

    in_dir = Path(args.input)
    files = sorted([p.name for p in in_dir.glob("*.png")])
    if not files:
        print("no images")
        return 1

    coords_path = Path(args.coords)
    rows = load_coords(coords_path)

    try:
        idx = files.index(args.start)
    except ValueError:
        idx = 0

    state = {"x": None, "y": None, "done": False}

    cv2.namedWindow("label", cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["x"], state["y"] = int(x), int(y)

    cv2.setMouseCallback("label", on_mouse)

    while 0 <= idx < len(files):
        name = files[idx]
        img = cv2.imread(str(in_dir / name), cv2.IMREAD_COLOR)
        if img is None:
            idx += 1
            continue

        h, w = img.shape[:2]
        while True:
            view = img.copy()
            row = rows.get(name)
            if row:
                cv2.circle(view, (int(row["cx"]), int(row["cy"])), 5, (0, 255, 255), -1)
            if state["x"] is not None and state["y"] is not None:
                cv2.circle(view, (state["x"], state["y"]), 4, (0, 0, 255), -1)

            text = f"{idx+1}/{len(files)} {name} | L-click: set | Enter: save+next | Backspace: prev | S: save file | Q: quit"
            cv2.putText(view, text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow("label", view)
            k = cv2.waitKey(30) & 0xFF

            if k in (ord("q"), 27):
                save_coords(coords_path, rows)
                cv2.destroyAllWindows()
                print(f"saved: {coords_path}")
                return 0
            if k in (13,):
                if state["x"] is not None and state["y"] is not None:
                    rows[name] = {
                        "file": name,
                        "w": w,
                        "h": h,
                        "cx": int(state["x"]),
                        "cy": int(state["y"]),
                        "method": "manual_click",
                    }
                    state["x"], state["y"] = None, None
                    idx += 1
                    break
            if k in (8,):  # backspace
                idx = max(0, idx - 1)
                state["x"], state["y"] = None, None
                break
            if k in (ord("s"),):
                save_coords(coords_path, rows)
                print(f"saved partial: {coords_path}")

    save_coords(coords_path, rows)
    cv2.destroyAllWindows()
    print(f"saved: {coords_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
