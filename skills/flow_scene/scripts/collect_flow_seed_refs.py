#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def _read_prompt(page) -> str:
    sels = [
        "textarea[aria-label*='prompt' i]",
        "textarea[placeholder*='prompt' i]",
        "[contenteditable='true'][role='textbox']",
        "textarea",
    ]
    best = ""
    for s in sels:
        try:
            loc = page.locator(s)
            n = min(loc.count(), 10)
            for i in range(n):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                try:
                    v = (el.input_value() or "").strip()
                except Exception:
                    try:
                        v = (el.inner_text() or "").strip()
                    except Exception:
                        v = ""
                if len(v) > len(best):
                    best = v
        except Exception:
            pass
    return re.sub(r"\s+", " ", best).strip()


def _role_of(prompt: str) -> str:
    p = prompt or ""
    if "Character: 무명" in p:
        return "mumyung"
    if "Character: 연화" in p:
        return "yeonhwa"
    if "Character: 조칠성" in p:
        return "jochilseong"
    if "Character: 강준" in p:
        return "kangjun"
    if "Character: 눈먼 노인 도사" in p:
        return "blind_old_wanderer"
    return "unknown"


def _extract_char_name(prompt: str) -> str:
    m = re.search(r"Character:\s*([^.]+)", prompt or "")
    return (m.group(1).strip() if m else "").strip()


def _load_char_name_to_id(story_id: str) -> dict[str, str]:
    pj = Path(f"work/{story_id}/out/project.json")
    if not pj.exists():
        return {}
    data = json.loads(pj.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for c in data.get("characters", []) or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        name = str(c.get("name") or "").strip()
        if name:
            out[name] = cid
        for a in c.get("aliases", []) or []:
            alias = str(a or "").strip()
            if alias:
                out[alias] = cid
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect top Flow project seed-card reference points.")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--top-n", type=int, default=20)
    args = ap.parse_args()

    out = {
        "story_id": args.story_id,
        "captured_at": dt.datetime.now().isoformat(),
        "items": [],
    }
    name_to_id = _load_char_name_to_id(args.story_id)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                u = pg.url or ""
                if "labs.google" in u and "/tools/flow/project/" in u:
                    page = pg
                    break
            if page:
                break
        if not page:
            print(json.dumps({"ok": False, "reason": "no_project_page"}, ensure_ascii=False))
            return 2

        page.bring_to_front()
        page.wait_for_timeout(800)
        cards = page.evaluate(
            """(topN) => {
              const rows=[...document.querySelectorAll('img')].map((el)=>{
                const r=el.getBoundingClientRect();
                return {src:(el.getAttribute('src')||'').trim(),nw:el.naturalWidth||0,nh:el.naturalHeight||0,x:r.x||0,y:r.y||0,w:r.width||0,h:r.height||0};
              }).filter(v=>v.src&&v.nw>=256&&v.nh>=256&&v.w>=80&&v.h>=80);
              const uniq=[]; const seen=new Set();
              for (const r of rows){ if (seen.has(r.src)) continue; seen.add(r.src); uniq.push(r); }
              uniq.sort((a,b)=>(a.y-b.y)||(a.x-b.x));
              return uniq.slice(0, Math.max(1, topN));
            }""",
            args.top_n,
        )

        for idx, c in enumerate(cards, start=1):
            x, y, w, h = float(c["x"]), float(c["y"]), float(c["w"]), float(c["h"])
            page.mouse.move(x + w * 0.45, y + h * 0.35)
            page.wait_for_timeout(120)
            page.mouse.click(x + 112, y + 22)
            page.wait_for_timeout(150)
            reuse = page.locator("button:has-text('프롬프트 재사용'), [role='menuitem']:has-text('프롬프트 재사용')").first
            if reuse.count() == 0:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                continue
            reuse.click(timeout=1200, force=True)
            page.wait_for_timeout(250)
            prompt = _read_prompt(page)
            cname = _extract_char_name(prompt)
            cid = name_to_id.get(cname, "")
            out["items"].append(
                {
                    "rank": idx,
                    "src": c["src"],
                    "role": _role_of(prompt),
                    "char_name": cname,
                    "char_id": cid,
                    "prompt": prompt,
                }
            )
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

    # Keep first seen item per known role.
    ordered = []
    seen_roles = set()
    for it in out["items"]:
        r = it["role"]
        if r == "unknown" or r in seen_roles:
            continue
        seen_roles.add(r)
        ordered.append(it)
    out["items"] = ordered

    path = Path(f"work/{args.story_id}/out/flow_seed_refs.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), "roles": [x["role"] for x in out["items"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
