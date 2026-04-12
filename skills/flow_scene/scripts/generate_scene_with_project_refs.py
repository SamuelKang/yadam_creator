#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _read_scene_prompt(story_id: str, scene_id: int) -> str:
    pj = Path(f"work/{story_id}/out/project.json")
    data = json.loads(pj.read_text(encoding="utf-8"))
    sc = data["scenes"][scene_id - 1]
    return (sc.get("llm_clip_prompt") or (sc.get("image") or {}).get("prompt_used") or "").strip()


def _read_scene_char_ids(story_id: str, scene_id: int) -> list[str]:
    pj = Path(f"work/{story_id}/out/project.json")
    data = json.loads(pj.read_text(encoding="utf-8"))
    sc = data["scenes"][scene_id - 1]
    return [str(x) for x in (sc.get("characters") or []) if str(x).strip()]


def _load_ref_srcs(story_id: str) -> list[dict]:
    p = Path(f"work/{story_id}/out/flow_seed_refs.json")
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for item in data.get("items", []):
        prompt = str(item.get("prompt") or "")
        src = str(item.get("src") or "")
        if not src:
            continue
        role = "unknown"
        if "Character: 무명" in prompt:
            role = "mumyung"
        elif "Character: 연화" in prompt:
            role = "yeonhwa"
        out.append(
            {
                "role": role,
                "src": src,
                "prompt": prompt,
                "char_id": str(item.get("char_id") or "").strip(),
                "char_name": str(item.get("char_name") or "").strip(),
            }
        )
    return out


def _find_flow_page(contexts):
    for ctx in contexts:
        for pg in ctx.pages:
            u = (pg.url or "").lower()
            if "labs.google" in u and "/tools/flow/project/" in u:
                return pg
    return None


def _dismiss_retry_conflict(page) -> None:
    sels = [
        "button:has-text('다시 시도')",
        "button:has-text('Retry')",
        "button[aria-label*='닫기']",
        "button[aria-label*='close' i]",
    ]
    for sel in sels:
        try:
            loc = page.locator(sel)
            n = min(loc.count(), 3)
            for i in range(n):
                try:
                    loc.nth(i).click(timeout=700, force=True)
                    page.wait_for_timeout(180)
                except Exception:
                    pass
        except Exception:
            pass


def _dismiss_overlays(page) -> None:
    # Close fullscreen/preview/menu states restored after refresh.
    for _ in range(4):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(140)
    # Click neutral area to release image-card focus.
    try:
        page.mouse.click(24, 24)
        page.wait_for_timeout(120)
    except Exception:
        pass


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
                loc.fill(prompt, timeout=1200)
            except Exception:
                loc.click(timeout=1200)
                page.keyboard.press("Meta+A")
                page.keyboard.type(prompt, delay=2)
            # Verify prompt actually landed in an editable input.
            try:
                cur = (loc.input_value(timeout=400) or "").strip()
            except Exception:
                try:
                    cur = (loc.inner_text(timeout=400) or "").strip()
                except Exception:
                    cur = ""
            if _norm(cur) != _norm(prompt):
                continue
            return True
        except Exception:
            continue
    return False


def _prompt_box_center(page) -> tuple[float, float] | None:
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
            bb = loc.bounding_box()
            if not bb:
                continue
            # Drop near the lower inside edge of prompt box (user requested lower target).
            return (bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] * 0.92)
        except Exception:
            continue
    return None


def _focus_prompt_box(page) -> bool:
    pt = _prompt_box_center(page)
    if not pt:
        return False
    try:
        page.mouse.move(pt[0], pt[1])
        page.mouse.click(pt[0], pt[1])
        page.wait_for_timeout(140)
        return True
    except Exception:
        return False


def _find_card_center_by_src(page, src: str) -> tuple[float, float] | None:
    try:
        cards = page.evaluate(
            """(src) => {
              const all=[...document.querySelectorAll('img')].map((el)=>{
                const r=el.getBoundingClientRect();
                return {src:(el.getAttribute('src')||'').trim(),x:r.x||0,y:r.y||0,w:r.width||0,h:r.height||0,nw:el.naturalWidth||0,nh:el.naturalHeight||0};
              }).filter(v=>v.src&&v.nw>=256&&v.nh>=256&&v.w>=80&&v.h>=80);
              const byExact=all.find(v=>v.src===src);
              if (byExact) return byExact;
              const tail=(src.split('name=').pop()||src.split('/').pop()||'').trim();
              if (!tail) return null;
              return all.find(v=>v.src.includes(tail)) || null;
            }""",
            src,
        )
    except Exception:
        cards = None
    if not cards:
        return None
    return (float(cards["x"]) + float(cards["w"]) * 0.5, float(cards["y"]) + float(cards["h"]) * 0.5)


def _scroll_to_top_for_refs(page) -> None:
    try:
        page.evaluate(
            """() => {
              try { window.scrollTo(0, 0); } catch {}
              const nodes = [...document.querySelectorAll('*')];
              for (const n of nodes) {
                try {
                  if (n.scrollHeight > n.clientHeight + 8) n.scrollTop = 0;
                } catch {}
              }
            }"""
        )
    except Exception:
        pass
    page.wait_for_timeout(200)


def _scroll_down_for_refs(page, amount: int = 1200) -> None:
    try:
        page.mouse.wheel(0, amount)
    except Exception:
        try:
            page.keyboard.press("PageDown")
        except Exception:
            pass
    page.wait_for_timeout(220)


def _find_card_center_by_src_with_scroll(page, src: str, max_scroll_steps: int = 36) -> tuple[float, float] | None:
    # Seed cards can move out of viewport as newer scene cards accumulate.
    _scroll_to_top_for_refs(page)
    for _ in range(max_scroll_steps):
        pt = _find_card_center_by_src(page, src)
        if pt:
            return pt
        _scroll_down_for_refs(page, amount=1400)
    return None


def _has_add_asset_hint(page) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                  function vis(el){
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 &&
                           r.left < (window.innerWidth || 1) && r.top < (window.innerHeight || 1);
                  }
                  const nodes = [...document.querySelectorAll('*')];
                  return nodes.some((n) => vis(n) && ((n.textContent || '').trim() === '소재 추가'));
                }"""
            )
        )
    except Exception:
        return False


def _drag(page, src_xy: tuple[float, float], dst_xy: tuple[float, float]) -> bool:
    sx, sy = src_xy
    dx, dy = dst_xy
    # Start with a deliberate move to avoid accidental click interpretation.
    page.mouse.move(sx, sy)
    page.wait_for_timeout(80)
    page.mouse.down()
    page.wait_for_timeout(90)
    steps = 18
    for i in range(1, steps + 1):
        x = sx + (dx - sx) * i / steps
        y = sy + (dy - sy) * i / steps
        page.mouse.move(x, y)
        page.wait_for_timeout(12)

    # User-requested gating: only drop when drag hint text '소재 추가' is visible.
    seen_hint = False
    deadline = time.time() + 2.5
    while time.time() < deadline:
        if _has_add_asset_hint(page):
            seen_hint = True
            break
        page.wait_for_timeout(80)

    # Keep holding briefly at target before release for stable drop.
    page.wait_for_timeout(1000)
    page.mouse.up()
    page.wait_for_timeout(240)
    return seen_hint


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


def _submit(page) -> bool:
    try:
        btn = page.get_by_role("button", name=re.compile(r"^(만들기|생성|create|generate)$", re.I)).first
        if btn.count() > 0 and btn.is_visible():
            btn.click(timeout=1200, force=True)
            return True
    except Exception:
        pass
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def _set_output_count_x1(page) -> bool:
    """Best-effort: force Flow output count to x1 / 1개 before submit."""
    # Open output-count control if a compact badge button is visible (x2/x3/2개/3개 etc.).
    opener_patterns = [
        r"\bx[23456789]\b",
        r"\b[2-9]\s*개\b",
        r"\b[2-9]\s*outputs?\b",
        r"variations?",
        r"출력",
        r"개수",
    ]
    try:
        buttons = page.get_by_role("button").all()
    except Exception:
        buttons = []
    opened = False
    for b in buttons[:120]:
        try:
            if not b.is_visible():
                continue
            t = (b.inner_text() or "").strip().lower()
            if any(re.search(p, t, re.I) for p in opener_patterns):
                b.click(timeout=800, force=True)
                page.wait_for_timeout(180)
                opened = True
                break
        except Exception:
            continue

    # Choose x1 / 1개 option.
    target_patterns = [r"^x1$", r"^1개$", r"^1\s*output$", r"^1$"]
    for pat in target_patterns:
        try:
            opt = page.get_by_role("button", name=re.compile(pat, re.I)).first
            if opt.count() > 0 and opt.is_visible():
                opt.click(timeout=800, force=True)
                page.wait_for_timeout(150)
                return True
        except Exception:
            pass
        try:
            opt = page.get_by_role("menuitem", name=re.compile(pat, re.I)).first
            if opt.count() > 0 and opt.is_visible():
                opt.click(timeout=800, force=True)
                page.wait_for_timeout(150)
                return True
        except Exception:
            pass

    # Close floating menu if we opened one but could not set explicitly.
    if opened:
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(80)
        except Exception:
            pass
    return False


def _detect_output_count(page) -> int | None:
    """Best-effort read of current output count badge/menu text. Returns 1..N or None."""
    patterns = [
        re.compile(r"\bx(?P<n>[1-9])\b", re.I),
        re.compile(r"\b(?P<n>[1-9])\s*개\b", re.I),
        re.compile(r"\b(?P<n>[1-9])\s*outputs?\b", re.I),
    ]
    try:
        buttons = page.get_by_role("button").all()
    except Exception:
        buttons = []
    seen: list[int] = []
    for b in buttons[:160]:
        try:
            if not b.is_visible():
                continue
            t = (b.inner_text() or "").strip().lower()
            if not t:
                continue
            for pat in patterns:
                m = pat.search(t)
                if m:
                    n = int(m.group("n"))
                    if 1 <= n <= 9:
                        seen.append(n)
                    break
        except Exception:
            continue
    if not seen:
        return None
    # Prefer explicit x1 if visible; otherwise use the smallest visible numeric badge.
    if 1 in seen:
        return 1
    return min(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate one scene by reusing in-project seed cards via drag-and-drop.")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--scene-id", type=int, required=True)
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--timeout-sec", type=float, default=240.0)
    ap.add_argument("--gen-poll-sec", type=float, default=10.0)
    ap.add_argument("--submit-only", action="store_true", help="Submit generation and return immediately; let verifier poll by prompt match.")
    args = ap.parse_args()

    prompt = _read_scene_prompt(args.story_id, args.scene_id)
    scene_char_ids = _read_scene_char_ids(args.story_id, args.scene_id)
    if not prompt:
        print(json.dumps({"ok": False, "reason": "missing_scene_prompt"}, ensure_ascii=False))
        return 2

    refs = _load_ref_srcs(args.story_id)
    refs_by_char = {r.get("char_id"): r for r in refs if r.get("char_id")}
    selected_refs = [refs_by_char[cid] for cid in scene_char_ids if cid in refs_by_char]
    if scene_char_ids and not selected_refs:
        print(
            json.dumps(
                {"ok": False, "reason": "missing_seed_refs", "scene_char_ids": scene_char_ids, "found": len(refs)},
                ensure_ascii=False,
            )
        )
        return 3

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        page = _find_flow_page(browser.contexts)
        if page is None:
            print(json.dumps({"ok": False, "reason": "no_flow_project_page"}, ensure_ascii=False))
            return 4
        page.bring_to_front()
        page.wait_for_timeout(600)
        _dismiss_retry_conflict(page)
        _dismiss_overlays(page)

        if not _set_prompt(page, prompt):
            print(json.dumps({"ok": False, "reason": "prompt_input_not_found"}, ensure_ascii=False))
            return 5

        # Prevent accidental multi-image generation (x2/x3): enforce x1 best-effort.
        x1_forced = _set_output_count_x1(page)
        out_count = _detect_output_count(page)
        print(
            json.dumps(
                {
                    "status": "pre_submit_controls",
                    "scene_id": args.scene_id,
                    "x1_forced": bool(x1_forced),
                    "detected_output_count": out_count,
                },
                ensure_ascii=False,
            )
        )
        if out_count is not None and int(out_count) > 1:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "output_count_not_one",
                        "scene_id": args.scene_id,
                        "detected_output_count": int(out_count),
                    },
                    ensure_ascii=False,
                )
            )
            return 10

        dst = _prompt_box_center(page)
        if not dst:
            print(json.dumps({"ok": False, "reason": "prompt_box_not_found"}, ensure_ascii=False))
            return 6

        dragged = []
        hint_seen = {}
        for r in selected_refs:
            role = str(r.get("role") or "unknown")
            src_xy = _find_card_center_by_src_with_scroll(page, r["src"])
            if not src_xy:
                print(
                    json.dumps(
                        {
                            "status": "ref_not_found_in_viewport",
                            "scene_id": args.scene_id,
                            "role": role,
                            "char_id": str(r.get("char_id") or ""),
                        },
                        ensure_ascii=False,
                    )
                )
                continue
            # Prevent card-click misfire before second drag: short pause + long cursor move.
            if dragged:
                try:
                    page.wait_for_timeout(260)
                    page.mouse.move(max(8, dst[0] - 260), max(8, dst[1] - 220))
                    page.wait_for_timeout(120)
                except Exception:
                    pass
            seen = _drag(page, src_xy, dst)
            dragged.append(role)
            hint_seen[role] = bool(seen)
            # Close potential card-preview/fullscreen and restore prompt-box focus.
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(120)
            except Exception:
                pass
            _focus_prompt_box(page)

        before = _count_large_images(page)
        print(
            json.dumps(
                {"status": "pre_submit_image_count", "scene_id": args.scene_id, "count": int(before)},
                ensure_ascii=False,
            )
        )
        if not _submit(page):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "submit_failed",
                        "dragged": dragged,
                        "add_asset_hint_seen": hint_seen,
                        "scene_char_ids": scene_char_ids,
                    },
                    ensure_ascii=False,
                )
            )
            return 7

        if args.submit_only:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "scene_id": args.scene_id,
                        "status": "submitted_only",
                        "dragged": dragged,
                        "add_asset_hint_seen": hint_seen,
                        "scene_char_ids": scene_char_ids,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        deadline = time.time() + max(20.0, args.timeout_sec)
        generated = False
        started = time.time()
        print(
            json.dumps(
                {
                    "status": "generation_watch_start",
                    "scene_id": args.scene_id,
                    "timeout_sec": float(args.timeout_sec),
                    "poll_sec": float(args.gen_poll_sec),
                },
                ensure_ascii=False,
            )
        )
        while time.time() < deadline:
            _dismiss_retry_conflict(page)
            now = _count_large_images(page)
            if now > before:
                generated = True
                delta = int(now - before)
                print(
                    json.dumps(
                        {
                            "status": "generation_detected",
                            "scene_id": args.scene_id,
                            "before": int(before),
                            "after": int(now),
                            "delta": delta,
                        },
                        ensure_ascii=False,
                    )
                )
                # Strict single-output guard for scene-by-scene mode.
                if delta > 1:
                    print(
                        json.dumps(
                            {"ok": False, "reason": "multi_outputs_detected", "scene_id": args.scene_id, "delta": delta},
                            ensure_ascii=False,
                        )
                    )
                    return 9
                break
            elapsed = int(time.time() - started)
            print(
                json.dumps(
                    {
                        "status": "waiting_generation",
                        "scene_id": args.scene_id,
                        "elapsed_sec": elapsed,
                        "poll_sec": float(args.gen_poll_sec),
                    },
                    ensure_ascii=False,
                )
            )
            page.wait_for_timeout(int(max(500, float(args.gen_poll_sec) * 1000)))

    if not generated:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "generation_timeout",
                    "dragged": dragged,
                    "add_asset_hint_seen": hint_seen,
                    "scene_char_ids": scene_char_ids,
                },
                ensure_ascii=False,
            )
        )
        return 8

    print(
        json.dumps(
            {
                "ok": True,
                "scene_id": args.scene_id,
                "dragged": dragged,
                "add_asset_hint_seen": hint_seen,
                "scene_char_ids": scene_char_ids,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
