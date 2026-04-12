#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from hashlib import sha1


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _find_first(page, selectors: list[str]):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                return loc, sel
        except Exception:
            pass
    return None, ""


def _collect_large_images(page):
    rows = []
    seen = set()
    for img in page.query_selector_all("img"):
        try:
            info = img.evaluate(
                """(el)=>({nw:el.naturalWidth||0,nh:el.naturalHeight||0,w:el.clientWidth||0,h:el.clientHeight||0,src:el.src||''})"""
            )
        except Exception:
            continue
        nw, nh, w, h = int(info.get("nw") or 0), int(info.get("nh") or 0), int(info.get("w") or 0), int(info.get("h") or 0)
        src = str(info.get("src") or "").strip()
        if nw >= 256 and nh >= 256 and src:
            if src in seen:
                continue
            seen.add(src)
            rows.append({"nw": nw, "nh": nh, "w": w, "h": h, "src": src})
    return rows


def probe_state():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        # Prefer Flow workspace tab when available.
        for pg in context.pages:
            u = (pg.url or "").lower()
            if ("labs.google" in u) and ("/tools/flow" in u):
                page = pg
                break
        if page is None:
            for pg in context.pages:
                if "gemini.google.com" in (pg.url or ""):
                    page = pg
                    break
        if page is None:
            raise SystemExit("FAIL: no Gemini page")

        page.bring_to_front()

        body_text = ""
        try:
            body_text = _norm(page.locator("body").inner_text(timeout=1200))
        except Exception:
            pass

        text_loc, text_sel = _find_first(
            page,
            [
                "textarea",
                "textarea[aria-label*='prompt' i]",
                "[contenteditable='true'][role='textbox']",
                "div[role='textbox'][contenteditable='true']",
            ],
        )

        input_present = text_loc is not None
        input_value = ""
        input_editable = None
        if text_loc is not None:
            try:
                input_value = _norm(text_loc.input_value())
            except Exception:
                try:
                    input_value = _norm(text_loc.inner_text())
                except Exception:
                    input_value = ""
            try:
                input_editable = bool(text_loc.is_enabled())
            except Exception:
                input_editable = None

        buttons = []
        try:
            all_btns = page.get_by_role("button").all()
            for b in all_btns[:120]:
                try:
                    name = _norm(b.inner_text())
                    al = _norm(b.get_attribute("aria-label") or "")
                    if name or al:
                        buttons.append({"text": name, "aria": al})
                except Exception:
                    pass
        except Exception:
            pass

        joined_btn = " | ".join(filter(None, [x.get("text", "") + " " + x.get("aria", "") for x in buttons])).lower()

        stop_signals = [
            "response stopped",
            "stopped",
            "대답이 중지되었습니다",
            "응답이 중지되었습니다",
            "중지되었습니다",
            "중지",
        ]
        running_signals = [
            "생성 중",
            "작성 중",
            "generating",
            "working",
        ]

        has_stopped_banner = any(s in body_text.lower() for s in [x.lower() for x in stop_signals])
        has_running_banner = any(s in body_text.lower() for s in [x.lower() for x in running_signals])
        stop_button_visible = any(k in joined_btn for k in ["중지", "stop"]) if joined_btn else False

        busy_count = 0
        for sel in ["[aria-busy='true']", "[role='progressbar']", "progress", "[data-loading='true']"]:
            try:
                busy_count += page.locator(sel).count()
            except Exception:
                pass

        large_imgs = _collect_large_images(page)
        dedup_srcs = []
        seen = set()
        for r in large_imgs:
            s = r["src"]
            if s in seen:
                continue
            seen.add(s)
            dedup_srcs.append(s)

        last_src = dedup_srcs[-1] if dedup_srcs else ""
        last_src_hash = sha1(last_src.encode("utf-8")).hexdigest() if last_src else ""

        state = {
            "ts": int(time.time()),
            "url": page.url,
            "input": {
                "present": input_present,
                "selector": text_sel,
                "editable": input_editable,
                "value_len": len(input_value),
                "value_preview": input_value[:160],
            },
            "signals": {
                "has_stopped_banner": has_stopped_banner,
                "has_running_banner": has_running_banner,
                "stop_button_visible": stop_button_visible,
                "busy_count": busy_count,
            },
            "images": {
                "large_count": len(large_imgs),
                "dedup_count": len(dedup_srcs),
                "last_src_hash": last_src_hash,
                "last_src_preview": last_src[:200],
            },
        }

        print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    probe_state()
