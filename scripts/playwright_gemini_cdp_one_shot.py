#!/usr/bin/env python3
"""
Gemini 1장 테스트 (CDP attach 방식)

방식:
- 사용자가 일반 Chrome를 원격 디버깅 포트로 직접 실행/로그인
- Playwright는 해당 Chrome에 CDP로 붙어서 자동 입력/생성 확인만 수행
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
import time


def _now_tag() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _wait_for_any_locator(page, selectors: list[str], timeout_ms: int):
    start = time.time()
    while int((time.time() - start) * 1000) < timeout_ms:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    return sel, loc
            except Exception:
                pass
        time.sleep(0.2)
    return None, None


def _set_prompt(page, prompt: str, timeout_ms: int) -> bool:
    textarea_selectors = [
        "textarea",
        "textarea[aria-label*='prompt' i]",
        "textarea[placeholder*='prompt' i]",
    ]
    contenteditable_selectors = [
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
        "[contenteditable='true']",
    ]

    _, loc = _wait_for_any_locator(page, textarea_selectors, timeout_ms)
    if loc is not None:
        loc.click()
        loc.fill(prompt)
        return True

    _, loc = _wait_for_any_locator(page, contenteditable_selectors, timeout_ms)
    if loc is not None:
        loc.click()
        page.keyboard.press("Meta+A")
        page.keyboard.type(prompt, delay=5)
        return True

    return False


def _click_generate(page, timeout_ms: int) -> bool:
    button_name_patterns = [
        r"^(generate|create|send)$",
        r"(generate|create image|이미지 생성|생성|전송|보내기)",
    ]
    for pat in button_name_patterns:
        try:
            btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
            btn.wait_for(state="visible", timeout=1200)
            btn.click()
            return True
        except Exception:
            pass

    css_candidates = [
        "button[aria-label*='Generate' i]",
        "button[aria-label*='Create' i]",
        "button[title*='Generate' i]",
        "button[type='submit']",
    ]
    _, btn = _wait_for_any_locator(page, css_candidates, timeout_ms)
    if btn is not None:
        btn.click()
        return True
    return False


def _press_enter_to_submit(page) -> bool:
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def _count_images(page) -> int:
    try:
        return page.locator("img").count()
    except Exception:
        return 0


def _count_large_images(page) -> int:
    try:
        return int(
            page.evaluate(
                """
                () => Array.from(document.images)
                  .filter(img => (img.naturalWidth || 0) >= 256 && (img.naturalHeight || 0) >= 256)
                  .length
                """
            )
        )
    except Exception:
        return 0


def _build_download_path(download_dir: pathlib.Path, story_id: str | None, scene_id: int | None) -> pathlib.Path:
    if story_id and scene_id:
        # Keep naming identical to clip file convention.
        name = f"{scene_id:03d}.png"
    else:
        name = f"{_now_tag()}_gemini_generated.png"
    return download_dir / name


def _save_largest_generated_image(page, out_path: pathlib.Path) -> bool:
    best = None
    best_score = -1
    for img in page.query_selector_all("img"):
        try:
            info = img.evaluate(
                """(el) => ({
                    nw: el.naturalWidth || 0,
                    nh: el.naturalHeight || 0,
                    w: el.clientWidth || 0,
                    h: el.clientHeight || 0
                })"""
            )
        except Exception:
            continue
        nw = int(info.get("nw") or 0)
        nh = int(info.get("nh") or 0)
        w = int(info.get("w") or 0)
        h = int(info.get("h") or 0)
        if nw < 256 or nh < 256 or w < 32 or h < 32:
            continue
        score = (nw * nh) + (w * h)
        if score > best_score:
            best_score = score
            best = img
    if best is None:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    best.screenshot(path=str(out_path))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini browser one-shot image generation test via CDP attach")
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--url", default="https://gemini.google.com/app")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--timeout-sec", type=int, default=120)
    ap.add_argument("--output-dir", default="work/browser_test")
    ap.add_argument("--download-dir", default="work/browser_test/downloads")
    ap.add_argument("--story-id", default=None)
    ap.add_argument("--scene-id", type=int, default=None)
    ap.add_argument("--require-manual-confirm", action="store_true")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    download_dir = pathlib.Path(args.download_dir)
    ts = _now_tag()
    shot_before = out_dir / f"{ts}_cdp_before.png"
    shot_after = out_dir / f"{ts}_cdp_after.png"

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("ERROR: playwright not installed.")
        return 2

    timeout_ms = max(1000, args.timeout_sec * 1000)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        except Exception as e:
            print(f"FAIL: cannot connect CDP endpoint {args.cdp_endpoint}: {e}")
            return 1

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for p0 in context.pages:
            if "gemini.google.com" in (p0.url or ""):
                page = p0
                break
        if page is None:
            page = context.new_page()
            page.goto(args.url, wait_until="domcontentloaded")
        elif args.url not in (page.url or ""):
            page.goto(args.url, wait_until="domcontentloaded")
        page.bring_to_front()

        page.screenshot(path=str(shot_before), full_page=True)
        if args.require_manual_confirm:
            print("Gemini 로그인/준비 상태인지 확인 후 Enter를 누르세요.")
            input("> ")
        else:
            print("INFO: manual confirm skipped; continuing automatically.")

        if not _set_prompt(page, args.prompt, timeout_ms=10000):
            page.screenshot(path=str(shot_after), full_page=True)
            print(f"FAIL: prompt input not found. screenshot={shot_after}")
            return 1

        before = _count_large_images(page)
        # Prefer Enter submission from the prompt box; button matching can hit non-composer UI.
        clicked = False
        if not _press_enter_to_submit(page):
            clicked = _click_generate(page, timeout_ms=10000)
            if not clicked:
                page.screenshot(path=str(shot_after), full_page=True)
                print(f"FAIL: generate submit action not available. screenshot={shot_after}")
                return 1

        deadline = time.time() + args.timeout_sec
        ok = False
        while time.time() < deadline:
            now = _count_large_images(page)
            if now > before:
                ok = True
                break
            # Fallback: if initial submit was button-based, retry Enter once.
            if clicked:
                _press_enter_to_submit(page)
                clicked = False
            time.sleep(1.0)

        page.screenshot(path=str(shot_after), full_page=True)
        save_path = _build_download_path(download_dir, args.story_id, args.scene_id)
        saved = _save_largest_generated_image(page, save_path)

        if ok:
            print("OK: generated image detected.")
            print(f"before={shot_before}")
            print(f"after={shot_after}")
            if saved:
                print(f"downloaded={save_path}")
            else:
                print("WARN: generated image file save failed.")
            return 0

        print("WARN: could not confirm image increase within timeout.")
        print(f"before={shot_before}")
        print(f"after={shot_after}")
        if saved:
            print(f"downloaded={save_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
