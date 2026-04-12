#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, datetime as dt, json, pathlib, re
from playwright.sync_api import sync_playwright


def norm(s:str)->str:
    return re.sub(r"\s+", " ", (s or "").strip())

def looks_token(s:str)->bool:
    s=(s or '').strip()
    return len(s)>=180 and (' ' not in s) and (re.fullmatch(r"[A-Za-z0-9._-]+", s or "") is not None)

def read_prompt(page)->str:
    sels=[
      "textarea[aria-label*='prompt' i]",
      "textarea[placeholder*='prompt' i]",
      "textarea[placeholder*='describe' i]",
      "textarea[placeholder*='묘사' i]",
      "[contenteditable='true'][role='textbox']",
      "div[role='textbox'][contenteditable='true']",
      "textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])",
      "textarea",
    ]
    best=(0,'')
    for sel in sels:
        try:
            loc=page.locator(sel); cnt=min(loc.count(), 10)
        except Exception:
            continue
        for i in range(cnt):
            try:
                el=loc.nth(i)
                if not el.is_visible():
                    continue
                try:
                    v=str(el.input_value(timeout=300) or '').strip()
                except Exception:
                    try: v=str(el.inner_text(timeout=300) or '').strip()
                    except Exception: v=''
                if (not v) or looks_token(v):
                    continue
                sc=0
                if 'Ghibli-inspired' in v: sc += 30
                if 'Primary subjects:' in v: sc += 20
                if 'Visible action:' in v: sc += 20
                if len(v)>120: sc += 10
                if sc>best[0]: best=(sc,v)
            except Exception:
                pass
    return best[1]


def _close_overlays(page) -> None:
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(100)
        except Exception:
            pass


def _is_card_list_state(page) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                  const vw = window.innerWidth || 1;
                  const vh = window.innerHeight || 1;
                  const thumbs = [...document.querySelectorAll('img')].filter(img => {
                    const r = img.getBoundingClientRect();
                    const nw = img.naturalWidth || 0, nh = img.naturalHeight || 0;
                    return nw >= 256 && nh >= 256 && r.width >= 80 && r.height >= 80 && r.width <= vw * 0.6 && r.height <= vh * 0.6;
                  });
                  const huge = [...document.querySelectorAll('img')].some(img => {
                    const r = img.getBoundingClientRect();
                    return r.width >= vw * 0.72 && r.height >= vh * 0.62;
                  });
                  return thumbs.length >= 2 && !huge;
                }"""
            )
        )
    except Exception:
        return False


def _ensure_card_list_state(page, story_id: str, scene_id: int) -> bool:
    for attempt in range(4):
        if _is_card_list_state(page):
            _dlog(story_id, scene_id, "card_list_state_ok", attempt=attempt, screenshot=_shot(page, story_id, scene_id, f"card_list_ok_{attempt}"))
            return True
        _dlog(story_id, scene_id, "card_list_state_retry", attempt=attempt, screenshot=_shot(page, story_id, scene_id, f"card_list_retry_{attempt}"))
        _close_overlays(page)
        try:
            page.mouse.click(24, 24)
            page.wait_for_timeout(150)
        except Exception:
            pass
    _dlog(story_id, scene_id, "card_list_state_fail", screenshot=_shot(page, story_id, scene_id, "card_list_fail"))
    return False


def _artifacts_dir(story_id: str) -> pathlib.Path:
    p = pathlib.Path(f"work/{story_id}/logs/flow_delete_artifacts")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _shot(page, story_id: str, scene_id: int, step: str) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", step)
    path = _artifacts_dir(story_id) / f"{scene_id:03d}_{ts}_{safe}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass
    return str(path)


def _dlog(story_id: str, scene_id: int, step: str, **kwargs) -> None:
    payload = {"status": "delete_step", "story_id": story_id, "scene_id": scene_id, "step": step}
    payload.update(kwargs)
    print(json.dumps(payload, ensure_ascii=False))


def _menu_open_now(page) -> tuple[bool, str]:
    probes = [
        "button:has-text('삭제')",
        "[role='menuitem']:has-text('삭제')",
        "button:has-text('Delete')",
        "[role='menuitem']:has-text('Delete')",
        "button:has-text('Remove')",
        "[role='menuitem']:has-text('Remove')",
    ]
    for sel in probes:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return True, sel
        except Exception:
            pass
    return False, ""


def _tail(src: str) -> str:
    s = (src or "").strip()
    if not s:
        return ""
    return (s.split("name=")[-1] if "name=" in s else s.split("/")[-1]).strip()


def _card_image_exists(page, src: str) -> bool:
    t = _tail(src)
    if not t:
        return False
    try:
        return bool(
            page.evaluate(
                """(tail) => [...document.querySelectorAll('img')].some(img => ((img.getAttribute('src')||'').includes(tail)))""",
                t,
            )
        )
    except Exception:
        return False


def _open_kebab_from_card(page, card: dict, story_id: str, scene_id: int, mode: str) -> bool:
    x = float(card["x"]); y = float(card["y"]); w = float(card["w"]); h = float(card["h"])
    _dlog(story_id, scene_id, "open_kebab_start", mode=mode, screenshot=_shot(page, story_id, scene_id, f"open_{mode}_start"))
    try:
        page.mouse.move(x + w * 0.45, y + h * 0.30)
        page.wait_for_timeout(150)
    except Exception:
        pass

    if mode == "force_hover":
        try:
            page.evaluate(
                """(c) => {
                  const cx=c.x+c.w*0.45, cy=c.y+c.h*0.30;
                  const el=document.elementFromPoint(cx, cy);
                  if(!el) return false;
                  for (const t of ['mouseenter','mouseover','mousemove']) {
                    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, clientX:cx, clientY:cy}));
                  }
                  return true;
                }""",
                {"x": x, "y": y, "w": w, "h": h},
            )
            page.wait_for_timeout(150)
        except Exception:
            pass

    if mode == "overlay_enable":
        try:
            page.evaluate(
                """(c) => {
                  const cx=c.x+c.w*0.45, cy=c.y+c.h*0.30;
                  const base=document.elementFromPoint(cx, cy);
                  if(!base) return false;
                  let root=base;
                  for(let i=0;i<6 && root && root.parentElement;i++){
                    const r=root.getBoundingClientRect();
                    if(r.left<=c.x+2 && r.top<=c.y+2 && r.right>=c.x+c.w-2 && r.bottom>=c.y+c.h-2) break;
                    root=root.parentElement;
                  }
                  if(!root) return false;
                  const nodes=[root, ...root.querySelectorAll('*')];
                  for(const n of nodes){
                    const r=n.getBoundingClientRect();
                    const midx=r.left+r.width*0.5, midy=r.top+r.height*0.5;
                    if(midx<c.x || midx>c.x+c.w || midy<c.y || midy>c.y+Math.max(28,c.h*0.4)) continue;
                    n.style.pointerEvents='auto';
                    n.style.opacity='1';
                    n.style.visibility='visible';
                  }
                  return true;
                }""",
                {"x": x, "y": y, "w": w, "h": h},
            )
            page.wait_for_timeout(150)
        except Exception:
            pass

    # Preferred: right-most button in the card top band.
    try:
        target = page.evaluate(
            """(c) => {
              const inCard=(r)=> (r.left+r.width*0.5)>=c.x && (r.left+r.width*0.5)<=c.x+c.w &&
                                  (r.top+r.height*0.5)>=c.y && (r.top+r.height*0.5)<=c.y+c.h;
              const topBand=(r)=> (r.top+r.height*0.5)<= (c.y + Math.max(28, c.h*0.4));
              const els=[...document.querySelectorAll('button,[role="button"]')].map(el=>{
                const r=el.getBoundingClientRect();
                const name=(el.getAttribute('aria-label')||el.textContent||'').trim();
                return {x:r.left,y:r.top,w:r.width,h:r.height,name};
              }).filter(v=>v.w>=10&&v.h>=10&&inCard({left:v.x,top:v.y,width:v.w,height:v.h})&&topBand({left:v.x,top:v.y,width:v.w,height:v.h}));
              if(!els.length) return null;
              els.sort((a,b)=> (b.x-a.x) || (a.y-b.y));
              const t=els[0];
              return {cx:t.x+t.w*0.5, cy:t.y+t.h*0.5, name:t.name};
            }""",
            {"x": x, "y": y, "w": w, "h": h},
        )
        if target and "cx" in target and "cy" in target:
            page.mouse.click(float(target["cx"]), float(target["cy"]))
            page.wait_for_timeout(220)
            ok, sel = _menu_open_now(page)
            if ok:
                _dlog(story_id, scene_id, "open_kebab_ok", mode=mode, selector=sel, screenshot=_shot(page, story_id, scene_id, f"open_{mode}_ok"))
                return True
    except Exception:
        pass

    # Fallback: click top-right points directly.
    for dx in (8, 12, 16, 22, 30, 40):
        try:
            page.mouse.click(x + w - dx, y + 14)
            page.wait_for_timeout(120)
        except Exception:
            pass
        ok, sel = _menu_open_now(page)
        if ok:
            _dlog(story_id, scene_id, "open_kebab_ok", mode=mode, selector=sel, screenshot=_shot(page, story_id, scene_id, f"open_{mode}_ok"))
            return True

    # Menu can be rendered in portal/body.
    ok, sel = _menu_open_now(page)
    if ok:
        _dlog(story_id, scene_id, "open_kebab_ok", mode=mode, selector=sel, screenshot=_shot(page, story_id, scene_id, f"open_{mode}_ok"))
        return True
    _dlog(story_id, scene_id, "open_kebab_fail", mode=mode, screenshot=_shot(page, story_id, scene_id, f"open_{mode}_fail"))
    return False


def _locate_card_by_src(page, src: str) -> dict | None:
    try:
        rows = page.evaluate(
            """(src) => {
              const items=[...document.querySelectorAll('img')].map((el)=>{
                const r=el.getBoundingClientRect();
                return {src:(el.getAttribute('src')||'').trim(),nw:el.naturalWidth||0,nh:el.naturalHeight||0,x:r.x||0,y:r.y||0,w:r.width||0,h:r.height||0};
              }).filter(v=>v.src&&v.nw>=256&&v.nh>=256&&v.w>=80&&v.h>=80);
              const exact=items.filter(v=>v.src===src);
              if (exact.length){ exact.sort((a,b)=>(a.y-b.y)||(a.x-b.x)); return exact[0]; }
              const tail=(src.split('name=').pop()||src.split('/').pop()||'').trim();
              if (!tail) return null;
              const tailRows=items.filter(v=>v.src.includes(tail));
              if (!tailRows.length) return null;
              tailRows.sort((a,b)=>(a.y-b.y)||(a.x-b.x));
              return tailRows[0];
            }""",
            src,
        )
        return rows if rows else None
    except Exception:
        return None


def _delete_card(page, card: dict) -> bool:
    src = str(card.get("src") or "").strip()
    story_id = str(card.get("_story_id") or "")
    scene_id = int(card.get("_scene_id") or 0)
    # Critical: proceed only in thumbnail-card list state.
    if not _ensure_card_list_state(page, story_id, scene_id):
        return False
    if src:
        fresh = _locate_card_by_src(page, src)
        if fresh:
            card = fresh
            card["src"] = src
        else:
            # One more attempt after forcing overlay close again.
            _close_overlays(page)
            try:
                page.mouse.click(24, 24)
                page.wait_for_timeout(120)
            except Exception:
                pass
            fresh = _locate_card_by_src(page, src)
            if fresh:
                card = fresh
                card["src"] = src
    try:
        x = float(card.get("x", 0.0))
        y = float(card.get("y", 0.0))
        w = max(40.0, float(card.get("w", 0.0)))
        h = max(40.0, float(card.get("h", 0.0)))
    except Exception:
        return False
    _dlog(story_id, scene_id, "delete_target_card", x=x, y=y, w=w, h=h, src_tail=_tail(src), screenshot=_shot(page, story_id, scene_id, "delete_target"))

    menu_opened = False
    for mode in ("hover", "force_hover", "corner_click", "overlay_enable"):
        if mode == "corner_click":
            # corner_click mode is encoded by _open_kebab_from_card fallback clicks after normal hover.
            mode = "hover"
        if _open_kebab_from_card(page, {"x": x, "y": y, "w": w, "h": h}, story_id, scene_id, mode):
            menu_opened = True
            break

    delete_locators = [
        "button:has-text('삭제')",
        "button:has-text('제거')",
        "[role='menuitem']:has-text('제거')",
        "button:has-text('프로젝트에서 삭제')",
        "[role='menuitem']:has-text('프로젝트에서 삭제')",
        "[role='menuitem']:has-text('삭제')",
        "button:has-text('Delete')",
        "[role='menuitem']:has-text('Delete')",
        "button:has-text('Remove')",
        "[role='menuitem']:has-text('Remove')",
    ]
    clicked = False
    for sel in delete_locators:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=1200, force=True)
                page.wait_for_timeout(180)
                clicked = True
                _dlog(story_id, scene_id, "delete_click", selector=sel, screenshot=_shot(page, story_id, scene_id, "delete_click"))
                break
        except Exception:
            pass
    if not clicked:
        # User-confirmed fallback: delete is the bottom item in the 3-dot menu.
        try:
            menu_items = page.locator("[role='menuitem']:visible, [role='menu'] button:visible, div[role='menu'] button:visible")
            n = int(menu_items.count())
            if n > 0:
                menu_items.nth(n - 1).click(timeout=1200, force=True)
                page.wait_for_timeout(180)
                clicked = True
                _dlog(story_id, scene_id, "delete_click_last_menuitem", menu_count=n, screenshot=_shot(page, story_id, scene_id, "delete_click_last"))
        except Exception:
            pass
    if not clicked:
        _dlog(story_id, scene_id, "delete_click_fail", menu_opened=menu_opened, screenshot=_shot(page, story_id, scene_id, "delete_click_fail"))
        _close_overlays(page)
        return False

    # Confirm delete if confirmation dialog appears.
    confirm_locators = [
        "button:has-text('삭제')",
        "button:has-text('제거')",
        "button:has-text('Delete')",
        "button:has-text('확인')",
        "button:has-text('Confirm')",
    ]
    for sel in confirm_locators:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=1200, force=True)
                page.wait_for_timeout(180)
                _dlog(story_id, scene_id, "delete_confirm_click", selector=sel, screenshot=_shot(page, story_id, scene_id, "delete_confirm"))
                break
        except Exception:
            pass

    # Verify card removed: src gone OR image count reduced.
    before = int(card.get("_before_count") or 0)
    after = before
    try:
        after = int(
            page.evaluate(
                """() => Array.from(document.images)
                  .filter(img => (img.naturalWidth||0)>=256 && (img.naturalHeight||0)>=256).length"""
            )
        )
    except Exception:
        pass
    gone = (not _card_image_exists(page, src)) if src else False
    ok = bool((after < before) or gone)
    _dlog(story_id, scene_id, "delete_verify", before=before, after=after, src_gone=gone, ok=ok, screenshot=_shot(page, story_id, scene_id, "delete_verify"))
    _close_overlays(page)
    return ok


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--story-id', required=True)
    ap.add_argument('--scene-id', type=int, required=True)
    ap.add_argument('--cdp-endpoint', default='http://127.0.0.1:9222')
    ap.add_argument('--url', default='https://labs.google/fx/tools/flow')
    ap.add_argument('--top-n', type=int, default=1)
    ap.add_argument('--wait-sec', type=float, default=20.0)
    ap.add_argument('--poll-sec', type=float, default=10.0)
    ap.add_argument('--delete-after-save', action='store_true')
    args=ap.parse_args()

    pj=pathlib.Path(f'work/{args.story_id}/out/project.json')
    data=json.loads(pj.read_text(encoding='utf-8'))
    exp=(data['scenes'][args.scene_id-1].get('llm_clip_prompt') or ((data['scenes'][args.scene_id-1].get('image') or {}).get('prompt_used') or '')).strip()
    if not exp:
        print(json.dumps({'ok':False,'reason':'missing_expected_prompt'}, ensure_ascii=False)); return 2

    with sync_playwright() as p:
        b=p.chromium.connect_over_cdp(args.cdp_endpoint)
        ctx=b.contexts[0] if b.contexts else b.new_context()
        page=None
        for pg in ctx.pages:
            u=(pg.url or '').lower()
            if 'labs.google' in u and '/tools/flow' in u:
                page=pg; break
        if page is None:
            print(json.dumps({'ok':False,'reason':'no_flow_page'}, ensure_ascii=False)); return 2
        page.bring_to_front()

        checked=[]
        matched=None
        end_ts = __import__('time').time() + max(0.0, float(args.wait_sec))
        while True:
            cards=page.evaluate('''() => {
              const rows=[...document.querySelectorAll('img')].map((el)=>{const r=el.getBoundingClientRect();return {src:(el.getAttribute('src')||'').trim(),nw:el.naturalWidth||0,nh:el.naturalHeight||0,x:r.x||0,y:r.y||0,w:r.width||0,h:r.height||0};}).filter(v=>v.src&&v.nw>=256&&v.nh>=256&&v.w>=80&&v.h>=80);
              const u=[]; const seen=new Set(); for(const r of rows){ if(seen.has(r.src)) continue; seen.add(r.src); u.push(r);} u.sort((a,b)=>(a.y-b.y)||(a.x-b.x)); return u;
            }''')[:max(1,args.top_n)]

            for c in cards:
                x,y,w,h=float(c['x']),float(c['y']),float(c['w']),float(c['h'])
                page.mouse.move(x+w*0.45, y+h*0.35)
                page.wait_for_timeout(180)
                page.mouse.click(x+112, y+22)
                page.wait_for_timeout(180)
                reuse=page.locator("button:has-text('프롬프트 재사용'), [role='menuitem']:has-text('프롬프트 재사용'), button:has-text('Reuse prompt'), [role='menuitem']:has-text('Reuse prompt')").first
                if reuse.count()==0:
                    try: page.keyboard.press('Escape'); page.wait_for_timeout(80)
                    except Exception: pass
                    continue
                reuse.click(timeout=1200, force=True)
                page.wait_for_timeout(260)
                got=read_prompt(page)
                ok=(norm(got)==norm(exp))
                checked.append({'src':c['src'][:90],'ok':ok,'preview':norm(got)[:120]})
                if ok:
                    matched=c
                    break
                try: page.keyboard.press('Escape'); page.wait_for_timeout(80)
                except Exception: pass
            if matched is not None:
                break
            if __import__('time').time() >= end_ts:
                break
            page.wait_for_timeout(int(max(200, float(args.poll_sec) * 1000)))

        if not matched:
            print(json.dumps({'ok':False,'reason':'no_exact_match_card','checked':checked[:6]}, ensure_ascii=False)); return 3

        before_delete_count = len(cards) if isinstance(cards, list) else 0
        b64=page.evaluate('''(src)=>{try{const imgs=[...document.images].filter(i=>(i.naturalWidth||0)>=256&&(i.naturalHeight||0)>=256&&((i.getAttribute('src')||'').trim()===src));if(!imgs.length)return '';const img=imgs[0];const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const g=c.getContext('2d');if(!g)return '';g.drawImage(img,0,0);const d=c.toDataURL('image/png');const i=d.indexOf(',');return i>0?d.slice(i+1):'';}catch(e){return '';}}''', matched['src'])
        if not b64:
            print(json.dumps({'ok':False,'reason':'empty_image_bytes','src':matched['src']}, ensure_ascii=False)); return 4
        out=pathlib.Path(f'work/{args.story_id}/clips/{args.scene_id:03d}.png')
        out.write_bytes(base64.b64decode(b64))
        deleted = False
        if args.delete_after_save:
            _close_overlays(page)
            m2 = dict(matched)
            m2["_story_id"] = args.story_id
            m2["_scene_id"] = args.scene_id
            m2["_before_count"] = before_delete_count
            deleted = _delete_card(page, m2)
        print(json.dumps({'ok':True,'scene':args.scene_id,'path':str(out),'src':matched['src'],'checked_count':len(checked),'deleted_after_save':bool(deleted)}, ensure_ascii=False))
        return 0

if __name__=='__main__':
    raise SystemExit(main())
