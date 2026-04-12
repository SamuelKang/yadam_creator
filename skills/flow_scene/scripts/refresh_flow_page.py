#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from playwright.sync_api import sync_playwright


def _find_flow_page(contexts, target_url: str):
    target_key = target_url.lower()
    for ctx in contexts:
        for pg in ctx.pages:
            u = (pg.url or "").lower()
            if "labs.google" in u and "/tools/flow" in u:
                return pg
            if target_key and target_key in u:
                return pg
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh existing Google Flow page over CDP.")
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--url", default="https://labs.google/fx/tools/flow")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        page = _find_flow_page(browser.contexts, args.url)
        if page is None:
            print(json.dumps({"ok": False, "reason": "no_flow_page"}, ensure_ascii=False))
            return 2
        page.bring_to_front()
        # User rule: always send ESC first to close preview/modal states.
        for _ in range(4):
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(140)
        page.reload(wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1200)
        print(json.dumps({"ok": True, "status": "flow_page_refreshed", "url": page.url}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
