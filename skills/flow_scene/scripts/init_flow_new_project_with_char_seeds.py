#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def _find_flow_page(contexts, target_url: str):
    for ctx in contexts:
        for pg in ctx.pages:
            u = (pg.url or "").lower()
            if "labs.google" in u and "/tools/flow" in u:
                return pg
    ctx = contexts[0] if contexts else None
    if ctx is None:
        return None
    pg = ctx.new_page()
    pg.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    return pg


def _click_text_button(page, patterns: list[str], timeout_ms: int = 1200) -> bool:
    regexes = [re.compile(p, re.I) for p in patterns]
    try:
        buttons = page.get_by_role("button").all()
    except Exception:
        return False
    for btn in buttons[:120]:
        try:
            if not btn.is_visible():
                continue
            txt = (btn.inner_text() or "").strip()
            if any(r.search(txt) for r in regexes):
                btn.click(timeout=timeout_ms, force=True)
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    return False


def _set_prompt(page, prompt: str) -> bool:
    sels = [
        "textarea[aria-label*='prompt' i]",
        "textarea[placeholder*='prompt' i]",
        "textarea[placeholder*='describe' i]",
        "textarea[placeholder*='묘사' i]",
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
        "textarea",
    ]
    for sel in sels:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            try:
                loc.fill(prompt, timeout=1000)
            except Exception:
                loc.click(timeout=1000)
                page.keyboard.press("Meta+A")
                page.keyboard.type(prompt, delay=2)
            return True
        except Exception:
            continue
    return False


def _submit(page) -> bool:
    if _click_text_button(page, [r"^만들기$", r"^create$", r"^generate$", r"arrow_forward"]):
        return True
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


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


def _ensure_workspace_ready(page, timeout_sec: float = 25.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            u = page.url or ""
        except Exception:
            u = ""
        if "/tools/flow/project/" not in u:
            _click_text_button(page, [r"^\+\s*새 프로젝트$", r"새 프로젝트", r"^\+\s*new project$", r"new project"])
            _click_text_button(page, [r"create with flow", r"flow에서 만들기", r"flow로 만들기"])
            page.wait_for_timeout(700)
            continue
        try:
            if page.locator("input[type=file]").count() > 0:
                return True
        except Exception:
            pass
        page.wait_for_timeout(700)
    return False


def _load_seed_targets(story_id: str, char_ids: list[str]) -> list[dict]:
    pj = Path(f"work/{story_id}/out/project.json")
    data = json.loads(pj.read_text(encoding="utf-8"))
    chars = {c.get("id"): c for c in data.get("characters", []) if isinstance(c, dict)}
    out: list[dict] = []
    for cid in char_ids:
        c = chars.get(cid) or {}
        name = str(c.get("name") or cid)
        role = str(c.get("role") or "").strip()
        visual_anchors = [str(x).strip() for x in (c.get("visual_anchors") or []) if str(x).strip()]
        wardrobe_anchors = [str(x).strip() for x in (c.get("wardrobe_anchors") or []) if str(x).strip()]
        aliases = [str(x).strip() for x in (c.get("aliases") or []) if str(x).strip()]
        img = (
            (c.get("image") or {}).get("path")
            or ((c.get("images") or {}).get("__default__") or {}).get("path")
        )
        path = None
        if img:
            p = Path(str(img))
            if not p.exists():
                # Fallback: some stories keep copied character refs under work/<story-id>/.
                base = p.name
                alt1 = Path(f"work/{story_id}/{base}")
                alt2 = Path(f"work/{story_id}/characters/{base}")
                if alt1.exists():
                    p = alt1
                elif alt2.exists():
                    p = alt2
            if p.exists():
                path = str(p.resolve())
        out.append(
            {
                "id": cid,
                "name": name,
                "role": role,
                "aliases": aliases,
                "visual_anchors": visual_anchors,
                "wardrobe_anchors": wardrobe_anchors,
                "path": path,
            }
        )
    return out


def _seed_prompt(item: dict) -> str:
    name = str(item.get("name") or "character")
    role = str(item.get("role") or "").strip()
    visuals = ", ".join(item.get("visual_anchors") or [])
    wardrobe = ", ".join(item.get("wardrobe_anchors") or [])
    alias = ", ".join(item.get("aliases") or [])
    desc_parts = [f"Character: {name}"]
    if alias:
        desc_parts.append(f"Aliases: {alias}")
    if role:
        desc_parts.append(f"Role: {role}")
    if visuals:
        desc_parts.append(f"Visual anchors: {visuals}")
    if wardrobe:
        desc_parts.append(f"Wardrobe anchors: {wardrobe}")
    desc_block = ". ".join(desc_parts)
    return (
        "Ghibli-inspired hand-drawn 2D animation, painterly illustrated look, non-photorealistic rendering. "
        f"Single-character consistency seed portrait for story reference. {desc_block}. "
        "One person only, centered waist-up portrait, clean silhouette, neutral but readable expression, "
        "soft natural light, Joseon-era Korean setting continuity, plain uncluttered background. "
        "No additional characters, no crowd, no modern objects, no text, no watermark."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a fresh Flow project and generate character seed cards first.")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--char-ids", default="char_001,char_002")
    ap.add_argument("--ignore-local-files", action="store_true")
    ap.add_argument("--reuse-current-project", action="store_true")
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--url", default="https://labs.google/fx/tools/flow")
    ap.add_argument("--timeout-sec", type=float, default=180.0)
    args = ap.parse_args()

    char_ids = [x.strip() for x in args.char_ids.split(",") if x.strip()]
    seeds = _load_seed_targets(args.story_id, char_ids)
    if not seeds:
        print(json.dumps({"ok": False, "reason": "no_seed_targets"}, ensure_ascii=False))
        return 2

    result = {"ok": True, "story_id": args.story_id, "seed_count": len(seeds), "items": []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        page = _find_flow_page(browser.contexts, args.url)
        if page is None:
            print(json.dumps({"ok": False, "reason": "no_flow_page"}, ensure_ascii=False))
            return 3
        page.bring_to_front()
        page.wait_for_timeout(800)

        if not args.reuse_current_project:
            _click_text_button(page, [r"^\+\s*새 프로젝트$", r"새 프로젝트", r"^\+\s*new project$", r"new project"])
            _click_text_button(page, [r"create with flow", r"flow에서 만들기", r"flow로 만들기"])
        if not _ensure_workspace_ready(page):
            print(json.dumps({"ok": False, "reason": "workspace_not_ready", "url": page.url}, ensure_ascii=False))
            return 4

        for item in seeds:
            status = {"char_id": item["id"], "name": item["name"], "ok": False}
            try:
                has_local_ref = bool(item.get("path")) and (not args.ignore_local_files)
                if has_local_ref:
                    inp = page.locator("input[type=file]").first
                    if inp.count() > 0:
                        inp.set_input_files(item["path"])
                        page.wait_for_timeout(500)
                prompt = _seed_prompt(item)
                if not _set_prompt(page, prompt):
                    status["reason"] = "prompt_input_not_found"
                    result["items"].append(status)
                    continue

                before = _count_large_images(page)
                if not _submit(page):
                    status["reason"] = "submit_failed"
                    result["items"].append(status)
                    continue

                deadline = time.time() + max(20.0, float(args.timeout_sec))
                generated = False
                while time.time() < deadline:
                    now = _count_large_images(page)
                    if now > before:
                        generated = True
                        break
                    page.wait_for_timeout(1000)

                if not generated:
                    status["reason"] = "generation_timeout"
                    result["items"].append(status)
                    continue

                status["ok"] = True
                status["used_local_ref"] = bool(has_local_ref)
                result["items"].append(status)
                page.wait_for_timeout(1200)
            except Exception as e:
                status["reason"] = f"exception:{type(e).__name__}"
                result["items"].append(status)

    if any(not x.get("ok") for x in result["items"]):
        result["ok"] = False
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
