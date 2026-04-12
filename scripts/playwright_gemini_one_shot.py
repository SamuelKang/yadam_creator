#!/usr/bin/env python3
"""
Gemini 웹 UI 1장 테스트 생성 스크립트.

의도:
- 사용자가 브라우저에서 로그인까지 수동으로 수행
- Enter 후 프롬프트 입력/생성 클릭/결과 이미지 생성 여부만 자동 확인

주의:
- Gemini UI 변경에 따라 selector 유지보수가 필요할 수 있음.
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
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=1400)
            return sel, loc
        except Exception:
            pass
        if int((time.time() - start) * 1000) > timeout_ms:
            break
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

    sel, loc = _wait_for_any_locator(page, textarea_selectors, timeout_ms)
    if loc is not None:
        loc.click()
        loc.fill(prompt)
        return True

    sel, loc = _wait_for_any_locator(page, contenteditable_selectors, timeout_ms)
    if loc is not None:
        loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.type(prompt, delay=5)
        return True

    return False


def _click_generate(page, timeout_ms: int) -> bool:
    # 텍스트/언어 변화 대응을 위해 버튼 후보를 넓게 둔다.
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
    for sel in css_candidates:
        try:
            btn = page.locator(sel).first
            btn.wait_for(state="visible", timeout=1000)
            btn.click()
            return True
        except Exception:
            pass
    return False


def _count_visible_images(page) -> int:
    candidates = [
        "img",
        "figure img",
        "[role='img'] img",
    ]
    count = 0
    for sel in candidates:
        try:
            n = page.locator(sel).count()
            if n > count:
                count = n
        except Exception:
            pass
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini browser one-shot image generation test")
    ap.add_argument("--url", default="https://gemini.google.com/app")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--timeout-sec", type=int, default=90)
    ap.add_argument("--output-dir", default="work/browser_test")
    ap.add_argument("--slow-mo-ms", type=int, default=0)
    args = ap.parse_args()

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _now_tag()
    shot_before = out_dir / f"{ts}_before.png"
    shot_after = out_dir / f"{ts}_after.png"

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("ERROR: playwright not installed. install with: pip install playwright && playwright install chromium")
        return 2

    timeout_ms = max(1000, args.timeout_sec * 1000)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=args.slow_mo_ms)
        context = browser.new_context(viewport={"width": 1440, "height": 920})
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        page.screenshot(path=str(shot_before), full_page=True)

        print("")
        print("브라우저에서 Gemini 로그인/준비를 완료한 뒤 터미널에서 Enter를 누르세요.")
        input("> ")

        ok_prompt = _set_prompt(page, args.prompt, timeout_ms=9000)
        if not ok_prompt:
            page.screenshot(path=str(shot_after), full_page=True)
            print(f"FAIL: prompt input element not found. screenshot={shot_after}")
            browser.close()
            return 1

        before_cnt = _count_visible_images(page)
        ok_click = _click_generate(page, timeout_ms=9000)
        if not ok_click:
            page.screenshot(path=str(shot_after), full_page=True)
            print(f"FAIL: generate button not found. screenshot={shot_after}")
            browser.close()
            return 1

        # 이미지 수 증가 또는 로딩 종료 후 이미지 존재 확인
        deadline = time.time() + args.timeout_sec
        success = False
        while time.time() < deadline:
            now_cnt = _count_visible_images(page)
            if now_cnt > before_cnt:
                success = True
                break
            # 기존 이미지가 있어도 추가 생성이 안 보이는 UI가 있어 fallback 확인
            try:
                if page.locator("img").count() >= 1:
                    # 생성 진행 중이면 보통 스피너/로더가 보임. 잠깐 더 대기.
                    pass
            except Exception:
                pass
            time.sleep(1.2)

        page.screenshot(path=str(shot_after), full_page=True)
        browser.close()

        if success:
            print("OK: image generation seems completed.")
            print(f"before={shot_before}")
            print(f"after={shot_after}")
            return 0

        print("WARN: could not confirm new image count within timeout.")
        print(f"before={shot_before}")
        print(f"after={shot_after}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

