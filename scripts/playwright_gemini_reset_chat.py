#!/usr/bin/env python3
from __future__ import annotations

import re
import time


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("FAIL: playwright not installed")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for pg in context.pages:
            if "gemini.google.com" in (pg.url or ""):
                page = pg
                break
        if page is None:
            print("FAIL: no Gemini page found")
            return 1
        page.bring_to_front()

        clicked = False
        try:
            btn = page.get_by_role("button", name=re.compile(r"(new chat|새 채팅|새 대화)", re.I)).first
            if btn.count() > 0:
                btn.click(timeout=1500)
                clicked = True
        except Exception:
            pass

        if not clicked:
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")

        time.sleep(1.5)
        print("OK: reset attempted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

