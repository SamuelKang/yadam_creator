#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
from typing import Any


def collect_large_images(page) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for img in page.query_selector_all("img"):
        try:
            info = img.evaluate(
                """(el)=>({nw:el.naturalWidth||0,nh:el.naturalHeight||0,w:el.clientWidth||0,h:el.clientHeight||0,src:el.src||''})"""
            )
        except Exception:
            continue
        nw = int(info.get("nw") or 0)
        nh = int(info.get("nh") or 0)
        w = int(info.get("w") or 0)
        h = int(info.get("h") or 0)
        src = str(info.get("src") or "").strip()
        if nw < 256 or nh < 256 or w < 32 or h < 32 or not src:
            continue
        rows.append({"nw": nw, "nh": nh, "w": w, "h": h, "src": src})
    return rows


def save_latest_by_src(page, out_path: pathlib.Path) -> bool:
    rows = collect_large_images(page)
    if not rows:
        return False
    latest_src = rows[-1]["src"]
    target = None
    for img in page.query_selector_all("img"):
        try:
            src = str(img.get_attribute("src") or "").strip()
        except Exception:
            continue
        if src == latest_src:
            target = img
    if target is None:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    target.screenshot(path=str(out_path))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Download currently shown latest Gemini image without sending new prompt")
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--url", default="https://gemini.google.com/app")
    ap.add_argument("--output", required=True, help="Output file path, e.g. work/story16/clips/012.png")
    args = ap.parse_args()

    out_path = pathlib.Path(args.output)

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("FAIL: playwright not installed")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for pg in context.pages:
            if "gemini.google.com" in (pg.url or ""):
                page = pg
                break
        if page is None:
            print("FAIL: no Gemini page found")
            return 1
        if args.url not in (page.url or ""):
            page.goto(args.url, wait_until="domcontentloaded")
        page.bring_to_front()

        if not save_latest_by_src(page, out_path):
            print("FAIL: no downloadable large image found on current page")
            return 1
        print(f"OK: downloaded={out_path}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

