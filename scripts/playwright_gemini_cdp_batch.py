#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import difflib
import json
import pathlib
import re
import subprocess
import sys
import time
from hashlib import sha1
from typing import Any
from urllib.parse import urlparse


def load_scene_prompts(project_json: pathlib.Path, start: int, end: int | None) -> list[tuple[int, str]]:
    data = json.loads(project_json.read_text(encoding="utf-8"))
    scenes = data.get("scenes") or []
    out: list[tuple[int, str]] = []
    for idx, sc in enumerate(scenes, start=1):
        sid = sc.get("id") if isinstance(sc.get("id"), int) else idx
        if sid < start:
            continue
        if end is not None and sid > end:
            continue
        prompt = (sc.get("llm_clip_prompt") or "").strip()
        if not prompt:
            prompt = ((sc.get("image") or {}).get("prompt_used") or "").strip()
        if not prompt:
            continue
        out.append((sid, prompt))
    return out


def merge_prompt_suffix(prompt: str, suffix: str) -> str:
    p = (prompt or "").strip()
    s = (suffix or "").strip()
    if not s:
        return p
    if not p:
        return s
    # Keep deterministic formatting for caching/review.
    if p.endswith("."):
        return f"{p} {s}"
    return f"{p}. {s}"


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def card_text_for_image_src(page, target_src: str) -> str:
    if not target_src:
        return ""
    try:
        txt = page.evaluate(
            """(src) => {
              function clean(t){ return String(t||'').replace(/\\s+/g,' ').trim(); }
              const imgs = [...document.querySelectorAll('img')];
              const target = imgs.find((el) => (el.getAttribute('src') || '').trim() === String(src || '').trim());
              if (!target) return '';
              let node = target;
              for (let i = 0; i < 16 && node; i++) {
                const t = clean(node.innerText || node.textContent || '');
                if (t && (t.includes('Primary subjects:') || t.includes('Visible action:') || t.length > 80)) {
                  return t.slice(0, 2000);
                }
                node = node.parentElement;
              }
              return '';
            }""",
            target_src,
        )
    except Exception:
        return ""
    return str(txt or "").strip()


def prompt_card_match_score(prompt: str, card_text: str) -> float:
    p = _norm_text(prompt)
    c = _norm_text(card_text)
    if not p or not c:
        return 0.0
    a = p[:1200]
    b = c[:1200]
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    bonus = 0.0
    if a[:120] and a[:120] in b:
        bonus += 0.2
    if "primary subjects:" in a and "primary subjects:" in b:
        bonus += 0.05
    if "visible action:" in a and "visible action:" in b:
        bonus += 0.05
    return min(1.0, ratio + bonus)


def click_prompt_reuse_for_image_src(page, target_src: str) -> bool:
    if not target_src:
        return False
    # First try: direct "reuse prompt" icon near target image card.
    try:
        rect = page.evaluate(
            """(src) => {
              const t = [...document.querySelectorAll('img')].find((el) => (el.getAttribute('src') || '').trim() === String(src || '').trim());
              if (!t) return null;
              const r = t.getBoundingClientRect();
              return { x: Number(r.left || 0), y: Number(r.top || 0), w: Number(r.width || 0), h: Number(r.height || 0) };
            }""",
            target_src,
        )
        if rect and float(rect.get("w") or 0) > 40 and float(rect.get("h") or 0) > 40:
            cx = float(rect["x"]) + min(float(rect["w"]) * 0.4, 180.0)
            cy = float(rect["y"]) + min(float(rect["h"]) * 0.3, 120.0)
            page.mouse.move(cx, cy)
            time.sleep(0.18)
            # Common Flow card overlay order: heart, reuse, more.
            for dx in (56.0, 84.0, 112.0):
                try:
                    page.mouse.click(float(rect["x"]) + dx, float(rect["y"]) + 22.0)
                    time.sleep(0.15)
                    got_after_icon = get_prompt_input_text(page).strip()
                    if got_after_icon and (not _looks_like_captcha_token(got_after_icon)) and len(got_after_icon) >= 40:
                        return True
                except Exception:
                    pass
            direct_reuse = bool(
                page.evaluate(
                    """(src) => {
                      function norm(v){ return String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase(); }
                      const reuseKeys = ['프롬프트 재사용', 'reuse prompt', 'reuse', '다시 사용', '다시 생성'];
                      const imgs = [...document.querySelectorAll('img')];
                      const target = imgs.find((el) => (el.getAttribute('src') || '').trim() === String(src || '').trim());
                      if (!target) return false;
                      let node = target;
                      for (let i = 0; i < 20 && node; i++) {
                        const btns = node.querySelectorAll("button, [role='button'], [aria-label], [title]");
                        for (const b of btns) {
                          const key = `${norm(b.innerText)} ${norm(b.getAttribute('aria-label'))} ${norm(b.getAttribute('title'))}`;
                          if (reuseKeys.some((k) => key.includes(k))) {
                            b.click();
                            return true;
                          }
                        }
                        node = node.parentElement;
                      }
                      return false;
                    }""",
                    target_src,
                )
            )
            if direct_reuse:
                return True
    except Exception:
        pass

    try:
        clicked = bool(
            page.evaluate(
                """(src) => {
                  function norm(v){ return String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase(); }
                  const images = [...document.querySelectorAll('img')];
                  const target = images.find((el) => (el.getAttribute('src') || '').trim() === String(src || '').trim());
                  if (!target) return false;

                  const moreKeys = ['더보기', '메뉴', '옵션', 'more', 'menu', 'options', 'more_vert'];
                  let host = target;
                  let opened = false;
                  for (let i = 0; i < 18 && host; i++) {
                    const btns = host.querySelectorAll("button, [role='button']");
                    for (const b of btns) {
                      const key = `${norm(b.innerText)} ${norm(b.getAttribute('aria-label'))} ${norm(b.getAttribute('data-testid'))}`;
                      if (moreKeys.some((k) => key.includes(k))) {
                        b.click();
                        opened = true;
                        break;
                      }
                    }
                    if (opened) break;
                    host = host.parentElement;
                  }
                  if (!opened) return false;

                  const reuseKeys = ['프롬프트 재사용', 'reuse prompt', 'reuse this prompt', 'use prompt', 'reuse'];
                  const nodes = [...document.querySelectorAll("button, [role='menuitem'], [role='button'], [aria-label], [aria-haspopup='menu']")];
                  const cand = nodes.find((n) => {
                    const key = `${norm(n.innerText)} ${norm(n.getAttribute('aria-label'))}`;
                    return reuseKeys.some((k) => key.includes(k));
                  });
                  if (!cand) return false;
                  cand.click();
                  return true;
                }""",
                target_src,
            )
        )
        if clicked:
            return True
    except Exception:
        pass

    # Fallback: click near target image top-right where card menu button often sits,
    # then select "프롬프트 재사용".
    try:
        rect = page.evaluate(
            """(src) => {
              const t = [...document.querySelectorAll('img')].find((el) => (el.getAttribute('src') || '').trim() === String(src || '').trim());
              if (!t) return null;
              const r = t.getBoundingClientRect();
              return { x: Number(r.left || 0), y: Number(r.top || 0), w: Number(r.width || 0), h: Number(r.height || 0) };
            }""",
            target_src,
        )
        if rect and float(rect.get("w") or 0) > 40 and float(rect.get("h") or 0) > 40:
            x = float(rect["x"]) + float(rect["w"]) - 18.0
            y = float(rect["y"]) + 18.0
            page.mouse.click(x, y)
            time.sleep(0.25)
            reuse_loc = page.locator(
                "button:has-text('프롬프트 재사용'), [role='menuitem']:has-text('프롬프트 재사용'), button:has-text('Reuse prompt'), [role='menuitem']:has-text('Reuse prompt')"
            ).first
            if reuse_loc.count() > 0:
                reuse_loc.click(timeout=1200, force=True)
                return True
    except Exception:
        pass
    return False


def reused_prompt_text_for_image_src(page, target_src: str, wait_sec: float = 4.0) -> str:
    if not target_src:
        return ""
    before = _norm_text(get_prompt_input_text(page))
    if not click_prompt_reuse_for_image_src(page, target_src):
        return ""
    deadline = time.time() + max(0.8, float(wait_sec))
    while time.time() < deadline:
        cur = get_prompt_input_text(page).strip()
        cur_norm = _norm_text(cur)
        if cur and cur_norm and cur_norm != before:
            return cur
        time.sleep(0.2)
    cur2 = get_prompt_input_text(page).strip()
    if cur2 and len(cur2) >= 40:
        return cur2
    return ""


def visible_image_candidates(page) -> list[dict[str, Any]]:
    try:
        rows = page.evaluate(
            """() => {
              const vw = window.innerWidth || 1;
              const vh = window.innerHeight || 1;
              const out = [];
              for (const img of document.images) {
                const r = img.getBoundingClientRect();
                const src = (img.getAttribute('src') || '').trim();
                const nw = img.naturalWidth || 0;
                const nh = img.naturalHeight || 0;
                const w = Math.max(0, r.width || 0);
                const h = Math.max(0, r.height || 0);
                const visible = r.bottom > 0 && r.right > 0 && r.left < vw && r.top < vh;
                if (!src || !visible) continue;
                if (nw < 512 || nh < 512 || w < 80 || h < 80) continue;
                out.push({
                  src,
                  x: Math.round(r.left || 0),
                  y: Math.round(r.top || 0),
                  w: Math.round(w),
                  h: Math.round(h),
                  area: Math.round(w * h),
                });
              }
              return out;
            }""",
        )
    except Exception:
        return []
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        src = str(row.get("src") or "").strip()
        if not src:
            continue
        prev = dedup.get(src)
        if prev is None or int(row.get("area") or 0) > int(prev.get("area") or 0):
            dedup[src] = row
    return list(dedup.values())


def choose_target_src_by_card_match(page, prompt: str, preferred_srcs: list[str] | None = None) -> tuple[str, float, str]:
    preferred = set(preferred_srcs or [])
    cands = visible_image_candidates(page)
    if not cands:
        return "", 0.0, ""
    # If we have explicit candidate srcs from this generation step, prioritize
    # them to prevent selecting visually similar older cards.
    if preferred:
        preferred_cands = [c for c in cands if str(c.get("src") or "") in preferred]
        if preferred_cands:
            cands = preferred_cands

    best_src = ""
    best_score = -1.0
    best_card = ""
    for c in cands:
        src = str(c.get("src") or "")
        card = card_text_for_image_src(page, src)
        score = prompt_card_match_score(prompt, card)
        # Prefer top-of-screen candidates when score ties (Flow often prepends new cards at top).
        y = int(c.get("y") or 0)
        top_bonus = 0.03 if y < 450 else 0.0
        pref_bonus = 0.03 if src in preferred else 0.0
        final_score = min(1.0, score + top_bonus + pref_bonus)
        if final_score > best_score:
            best_score = final_score
            best_src = src
            best_card = card
    return best_src, max(0.0, best_score), best_card


def best_card_match_anywhere(page, prompt: str) -> tuple[str, float, str]:
    best_src = ""
    best_score = 0.0
    best_card = ""
    for src in collect_large_image_srcs(page):
        card = card_text_for_image_src(page, src)
        score = prompt_card_match_score(prompt, card)
        if score > best_score:
            best_src = src
            best_score = score
            best_card = card
    return best_src, best_score, best_card


def wait_for_any_locator(page, selectors: list[str], timeout_ms: int):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    return loc
            except Exception:
                pass
        time.sleep(0.2)
    return None


def wait_for_any_locator_in_frames(page, selectors: list[str], timeout_ms: int):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        frames = [page] + list(page.frames)
        for fr in frames:
            for sel in selectors:
                try:
                    loc = fr.locator(sel).first
                    if loc.count() > 0:
                        return loc
                except Exception:
                    pass
        time.sleep(0.2)
    return None


def has_visible_prompt_input(page) -> bool:
    selectors = [
        "textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])",
        "textarea[aria-label*='prompt' i]",
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            cnt = min(loc.count(), 8)
        except Exception:
            continue
        for i in range(cnt):
            try:
                cand = loc.nth(i)
                if cand.is_visible():
                    return True
            except Exception:
                continue
    return False


def list_candidate_locators_in_frames(page, selectors: list[str], max_each: int = 5):
    out = []
    frames = [page] + list(page.frames)
    for fr in frames:
        for sel in selectors:
            try:
                loc_all = fr.locator(sel)
                cnt = min(loc_all.count(), max_each)
            except Exception:
                continue
            for i in range(cnt):
                try:
                    out.append(loc_all.nth(i))
                except Exception:
                    continue
    return out


def ensure_image_mode(page) -> bool:
    labels = [
        r"이미지 만들기",
        r"이미지 생성",
        r"create image",
        r"generate image",
    ]
    # First, if already in image mode, this is a no-op.
    try:
        body = str(page.locator("body").inner_text(timeout=700)).lower()
    except Exception:
        body = ""
    if ("이미지 만들기" in body) or ("create image" in body and "selected" in body):
        return True

    # Try direct button selection by visible name.
    for pat in labels:
        try:
            btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
            if btn.count() > 0:
                btn.click(timeout=1200)
                time.sleep(0.5)
                return True
        except Exception:
            pass

    # Try menu-like openers then choose image item.
    openers = [r"도구", r"tools", r"모드", r"mode", r"앱", r"apps"]
    for op in openers:
        try:
            ob = page.get_by_role("button", name=re.compile(op, re.I)).first
            if ob.count() > 0:
                ob.click(timeout=1000)
                time.sleep(0.4)
                for pat in labels:
                    try:
                        item = page.get_by_role("menuitem", name=re.compile(pat, re.I)).first
                        if item.count() > 0:
                            item.click(timeout=1200)
                            time.sleep(0.5)
                            return True
                    except Exception:
                        pass
                for pat in labels:
                    try:
                        item = page.get_by_role("button", name=re.compile(pat, re.I)).first
                        if item.count() > 0:
                            item.click(timeout=1200)
                            time.sleep(0.5)
                            return True
                    except Exception:
                        pass
                # Fallback: tool panel item may not expose role, click plain text node.
                for pat in labels:
                    try:
                        txt = page.get_by_text(re.compile(pat, re.I)).first
                        if txt.count() > 0:
                            txt.click(timeout=1200)
                            time.sleep(0.5)
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
    return False


def collect_state(page) -> dict[str, Any]:
    try:
        body = str(page.locator("body").inner_text(timeout=700)).lower()
    except Exception:
        body = ""

    input_present = False
    input_editable = None
    input_selectors = [
        "textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])",
        "textarea[aria-label*='prompt' i]",
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
    ]
    for sel in input_selectors:
        try:
            loc = page.locator(sel)
            cnt = min(loc.count(), 8)
        except Exception:
            pass
        else:
            for i in range(cnt):
                try:
                    cand = loc.nth(i)
                    if not cand.is_visible():
                        continue
                    input_present = True
                    try:
                        input_editable = bool(cand.is_enabled())
                    except Exception:
                        input_editable = None
                    break
                except Exception:
                    continue
            if input_present:
                break

    stop_button_visible = False
    try:
        buttons = page.get_by_role("button").all()
        joined = []
        for b in buttons[:120]:
            try:
                joined.append((str(b.inner_text() or "") + " " + str(b.get_attribute("aria-label") or "")).lower())
            except Exception:
                continue
        blob = " | ".join(joined)
        stop_button_visible = ("stop" in blob) or ("중지" in blob)
    except Exception:
        pass

    busy_count = 0
    for sel in ["[aria-busy='true']", "[role='progressbar']", "progress", "[data-loading='true']"]:
        try:
            busy_count += page.locator(sel).count()
        except Exception:
            pass

    has_running_banner = any(
        k in body
        for k in [
            "generating",
            "working",
            "loading",
            "processing",
            "rendering",
            "creating",
            "생성 중",
            "진행 중",
            "작성 중",
            "로딩 중",
            "응답 생성 중",
            "답변 생성 중",
            "대답 생성 중",
            "나노 바나나2 로딩 중",
            "나노바나나2 로딩 중",
        ]
    )
    has_progress_pct = bool(re.search(r"\b(?:[1-9]?\d|100)\s*%\b", body))
    has_inflight_hint = has_running_banner or has_progress_pct
    has_stopped_banner = any(k in body for k in ["response stopped", "stopped", "대답이 중지되었습니다", "응답이 중지되었습니다", "중지되었습니다"])

    srcs = collect_large_image_srcs(page)
    last_src = srcs[-1] if srcs else ""
    last_src_hash = sha1(last_src.encode("utf-8")).hexdigest() if last_src else ""
    return {
        "input_present": input_present,
        "input_editable": input_editable,
        "stop_button_visible": stop_button_visible,
        "busy_count": busy_count,
        "has_running_banner": has_running_banner,
        "has_inflight_hint": has_inflight_hint,
        "has_stopped_banner": has_stopped_banner,
        "large_image_count": len(srcs),
        "last_src_hash": last_src_hash,
    }


def wait_until_idle(page, timeout_sec: float, stable_sec: float, poll_sec: float) -> tuple[bool, dict[str, Any]]:
    deadline = time.time() + timeout_sec
    idle_since: float | None = None
    last = {}
    while time.time() < deadline:
        st = collect_state(page)
        last = st
        idle = (
            st.get("input_present") is True
            and st.get("input_editable") is not False
            # Gemini UI can keep a generic "stop" control visible even when truly idle.
            and not (st.get("stop_button_visible") is True and st.get("has_running_banner") is True)
            and int(st.get("busy_count") or 0) <= 2
            and st.get("has_running_banner") is False
            and st.get("has_inflight_hint") is False
        )
        if idle:
            if idle_since is None:
                idle_since = time.time()
            if (time.time() - idle_since) >= stable_sec:
                return True, st
        else:
            idle_since = None
        time.sleep(max(0.2, poll_sec))
    return False, last


def is_idle_state(st: dict[str, Any]) -> bool:
    return (
        st.get("input_present") is True
        and st.get("input_editable") is not False
        and not (st.get("stop_button_visible") is True and st.get("has_running_banner") is True)
        and int(st.get("busy_count") or 0) <= 2
        and st.get("has_running_banner") is False
        and st.get("has_inflight_hint") is False
    )


def has_generation_start_signal(st: dict[str, Any]) -> bool:
    # Start signal should not depend on a single brittle indicator.
    return bool(
        st.get("has_running_banner")
        or st.get("has_inflight_hint")
        or st.get("stop_button_visible")
        or int(st.get("busy_count") or 0) > 2
        or st.get("input_editable") is False
    )


def _looks_like_captcha_token(value: str) -> bool:
    v = (value or "").strip()
    if len(v) < 180:
        return False
    if " " in v or "\n" in v or "\t" in v:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{180,}", v))


def _extract_best_prompt_like_text(page) -> str:
    try:
        txt = page.evaluate(
            """() => {
              function norm(v){ return String(v || '').replace(/\\s+/g, ' ').trim(); }
              function isToken(v){
                const t = norm(v);
                if (t.length < 180) return false;
                if (/\\s/.test(t)) return false;
                return /^[A-Za-z0-9._-]{180,}$/.test(t);
              }
              const sels = ["textarea", "[contenteditable='true']", "[role='textbox']", "input[type='text']"];
              const nodes = [];
              for (const sel of sels) {
                for (const el of document.querySelectorAll(sel)) nodes.push(el);
              }
              let best = "";
              let bestScore = -1e9;
              for (const el of nodes) {
                const id = norm(el.getAttribute('id')).toLowerCase();
                const nm = norm(el.getAttribute('name')).toLowerCase();
                const cl = norm(el.getAttribute('class')).toLowerCase();
                let v = "";
                if (typeof el.value === "string" && el.value) v = norm(el.value);
                if (!v) v = norm(el.innerText || el.textContent || "");
                if (!v || v.length < 24) continue;
                let s = 0;
                if (v.length >= 60) s += 5;
                if (v.includes("Primary subjects:")) s += 40;
                if (v.includes("Visible action:")) s += 40;
                if (/[.!?]\\s/.test(v)) s += 8;
                if (v.includes("Joseon-era") || v.includes("Ghibli-inspired")) s += 8;
                if (isToken(v)) s -= 200;
                if (id.includes("recaptcha") || nm.includes("recaptcha") || cl.includes("recaptcha")) s -= 200;
                if (s > bestScore) {
                  bestScore = s;
                  best = v;
                }
              }
              return best;
            }"""
        )
        best = str(txt or "").strip()
        if best:
            return best
    except Exception:
        return ""

    # Last-resort fallback: parse body text for prompt-like segments.
    try:
        body = str(page.locator("body").inner_text(timeout=1200) or "")
    except Exception:
        return ""
    body_norm = re.sub(r"\s+", " ", body).strip()
    if not body_norm:
        return ""
    m = re.search(r"(Primary subjects:.*?Visible action:.*?)(?:Mood:|Joseon-era|no modern objects|$)", body_norm, flags=re.IGNORECASE)
    if m:
        s = m.group(1).strip()
        if len(s) >= 80:
            return s
    m2 = re.search(r"(Ghibli-inspired.*?no visible text.*?(?:speech bubbles|captions).?)", body_norm, flags=re.IGNORECASE)
    if m2:
        s2 = m2.group(1).strip()
        if len(s2) >= 80:
            return s2
    return ""


def get_prompt_input_text(page) -> str:
    selectors = [
        "textarea[aria-label*='prompt' i]",
        "textarea[placeholder*='prompt' i]",
        "textarea[placeholder*='describe' i]",
        "textarea[placeholder*='묘사' i]",
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
        "textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])",
        "textarea",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            cnt = min(loc.count(), 8)
        except Exception:
            continue
        for i in range(cnt):
            try:
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                try:
                    aid = str(el.get_attribute("id") or "").lower()
                    anm = str(el.get_attribute("name") or "").lower()
                    acl = str(el.get_attribute("class") or "").lower()
                    if ("recaptcha" in aid) or ("recaptcha" in anm) or ("recaptcha" in acl):
                        continue
                except Exception:
                    pass
                try:
                    v = str(el.input_value() or "").strip()
                except Exception:
                    v = str(el.inner_text() or "").strip()
                if _looks_like_captcha_token(v):
                    continue
                if len(v) >= 1:
                    return v
            except Exception:
                continue
    fb = _extract_best_prompt_like_text(page)
    if fb and not _looks_like_captcha_token(fb):
        return fb
    return ""


def prompt_required_warning_visible(page) -> bool:
    try:
        text = str(page.locator("body").inner_text(timeout=600)).lower()
    except Exception:
        return False
    keys = [
        "프롬프트를 입력해야 합니다",
        "프롬프트를 입력해",
        "enter a prompt",
        "please enter a prompt",
        "prompt is required",
    ]
    return any(k in text for k in keys)


def prompt_text_matches(page, prompt: str, min_prefix_len: int = 40) -> bool:
    cur = get_prompt_input_text(page)
    if not cur:
        return False
    p = _norm_text(prompt)
    c = _norm_text(cur)
    if not p or not c:
        return False
    prefix = p[:max(20, min_prefix_len)]
    return (prefix in c) or (c in p and len(c) >= max(20, min_prefix_len))


def set_prompt(page, prompt: str) -> bool:
    textarea_selectors = [
        "textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])",
        "textarea[aria-label*='prompt' i]",
        "textarea[placeholder*='prompt' i]",
        "textarea[placeholder*='describe' i]",
        "textarea[placeholder*='묘사' i]",
    ]
    contenteditable_selectors = [
        "[contenteditable='true'][role='textbox']",
        "div[role='textbox'][contenteditable='true']",
        "[contenteditable='true']",
        "[role='textbox']",
        "div[aria-label*='prompt' i]",
        "div[aria-label*='describe' i]",
    ]

    trace: list[str] = []

    # Flow option popovers can intercept pointer events on the prompt box.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)
        page.keyboard.press("Escape")
    except Exception:
        pass

    # Fast-path fallback for Flow-like UIs where textarea exists but click focus is blocked.
    try:
        direct_ok = bool(
            page.evaluate(
                """(val) => {
                  const el = document.querySelector(\"textarea:not([id*='g-recaptcha']):not([name*='g-recaptcha'])\");
                  if (!el) return false;
                  el.value = String(val || '');
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }""",
                prompt,
            )
        )
        if direct_ok and prompt_text_matches(page, prompt):
            return True
    except Exception:
        pass

    area_candidates = list_candidate_locators_in_frames(page, textarea_selectors, max_each=8)
    if area_candidates:
        for loc in area_candidates:
            try:
                if hasattr(loc, "is_visible") and not loc.is_visible():
                    continue
            except Exception:
                pass
            # Try non-click fill path first (works on some Flow textarea states).
            try:
                loc.fill(prompt, timeout=1500)
                if prompt_text_matches(page, prompt):
                    return True
            except Exception:
                try:
                    loc.evaluate(
                        """(el, val) => { el.value = val; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }""",
                        prompt,
                    )
                    if prompt_text_matches(page, prompt):
                        return True
                except Exception:
                    pass
            # Fallback with click focus.
            for _ in range(2):
                try:
                    loc.scroll_into_view_if_needed(timeout=1200)
                except Exception:
                    pass
                try:
                    loc.click(timeout=1500, force=True)
                except Exception:
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)
                    except Exception:
                        pass
                    trace.append("textarea_click_failed")
                    continue
                try:
                    page.keyboard.press("Meta+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(prompt, delay=2)
                    try:
                        page.evaluate(
                            """() => {
                              const a = document.activeElement;
                              if (!a) return;
                              a.dispatchEvent(new Event('input', { bubbles: true }));
                              a.dispatchEvent(new Event('change', { bubbles: true }));
                            }"""
                        )
                    except Exception:
                        pass
                    if prompt_text_matches(page, prompt):
                        return True
                except Exception:
                    trace.append("textarea_fill_all_failed")
                    continue

    ce_candidates = list_candidate_locators_in_frames(page, contenteditable_selectors, max_each=8)
    if ce_candidates:
        for loc in ce_candidates:
            try:
                if hasattr(loc, "is_visible") and not loc.is_visible():
                    continue
            except Exception:
                pass
            for _ in range(2):
                try:
                    loc.scroll_into_view_if_needed(timeout=1200)
                except Exception:
                    pass
                try:
                    loc.click(timeout=1500, force=True)
                except Exception:
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)
                    except Exception:
                        pass
                    trace.append("contenteditable_click_failed")
                    continue
                try:
                    page.keyboard.press("Meta+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(prompt, delay=2)
                    try:
                        page.evaluate(
                            """() => {
                              const a = document.activeElement;
                              if (!a) return;
                              a.dispatchEvent(new Event('input', { bubbles: true }));
                              a.dispatchEvent(new Event('change', { bubbles: true }));
                            }"""
                        )
                    except Exception:
                        pass
                    if prompt_text_matches(page, prompt):
                        return True
                except Exception:
                    try:
                        page.keyboard.type(prompt, delay=3)
                        if prompt_text_matches(page, prompt):
                            return True
                    except Exception:
                        trace.append("contenteditable_type_failed")
                        continue
    counts: dict[str, int | str] = {}
    for sel in textarea_selectors + contenteditable_selectors:
        try:
            counts[sel] = page.locator(sel).count()
        except Exception as e:
            counts[sel] = f"err:{e}"
    print(f"DEBUG set_prompt failed: trace={trace} counts={counts}")
    return False


def count_large_images(page) -> int:
    try:
        return int(
            page.evaluate(
                """
                () => {
                  const set = new Set();
                  for (const img of Array.from(document.images)) {
                    const nw = img.naturalWidth || 0;
                    const nh = img.naturalHeight || 0;
                    const src = (img.getAttribute('src') || '').trim();
                    if (nw >= 256 && nh >= 256 && src) set.add(src);
                  }
                  return set.size;
                }
                """
            )
        )
    except Exception:
        return 0


def collect_large_image_srcs(page) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    try:
        imgs = page.query_selector_all("img")
    except Exception:
        # Page may be navigating/re-rendering; treat as temporarily empty.
        return out
    for img in imgs:
        try:
            info = img.evaluate(
                """(el) => ({ nw: el.naturalWidth || 0, nh: el.naturalHeight || 0, w: el.clientWidth || 0, h: el.clientHeight || 0 })"""
            )
            src = str(img.get_attribute("src") or "").strip()
        except Exception:
            continue
        nw = int(info.get("nw") or 0)
        nh = int(info.get("nh") or 0)
        if nw < 256 or nh < 256 or not src:
            continue
        if src in seen:
            continue
        seen.add(src)
        out.append(src)
    return out


def save_newest_generated_image(page, out_path: pathlib.Path, new_srcs: list[str]) -> bool:
    if not new_srcs:
        return False
    target_src = new_srcs[-1]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Retry because Gemini DOM can re-render right after generation.
    for _ in range(4):
        target = None
        try:
            imgs = page.query_selector_all("img")
        except Exception:
            imgs = []
        for img in imgs:
            try:
                src = str(img.get_attribute("src") or "").strip()
            except Exception:
                continue
            if src == target_src:
                target = img
        if target is None:
            time.sleep(0.4)
            continue
        try:
            target.screenshot(path=str(out_path))
            return True
        except Exception:
            time.sleep(0.5)
            continue
    return False


def newest_download_file(download_dir: pathlib.Path) -> pathlib.Path | None:
    files = sorted(download_dir.glob("Gemini_Generated_Image*"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def md5_file(path: pathlib.Path) -> str:
    import hashlib

    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_prev_scene_file(clips_dir: pathlib.Path, sid: int) -> pathlib.Path | None:
    if sid <= 1:
        return None
    prev = sid - 1
    for ext in ("png", "jpg", "jpeg"):
        p = clips_dir / f"{prev:03d}.{ext}"
        if p.exists():
            return p
    return None


def same_as_prev_scene(clips_dir: pathlib.Path, sid: int, out_path: pathlib.Path) -> tuple[bool, str]:
    if not out_path.exists():
        return False, ""
    prev_path = find_prev_scene_file(clips_dir, sid)
    if prev_path is None:
        return False, ""
    try:
        a = md5_file(out_path)
        b = md5_file(prev_path)
    except Exception:
        return False, ""
    if a == b:
        return True, str(prev_path)

    # Near-duplicate guard: visually same images can differ by tiny encoding noise.
    try:
        from PIL import Image
        import numpy as np

        def _ahash(path: pathlib.Path, size: int = 16):
            img = Image.open(path).convert("L").resize((size, size))
            arr = np.array(img, dtype=np.float32)
            bits = (arr > float(arr.mean())).astype(np.uint8).flatten()
            return bits

        def _hamming(x, y) -> int:
            return int(np.count_nonzero(x != y))

        i1 = np.array(Image.open(out_path).convert("RGB"), dtype=np.int16)
        i2 = np.array(Image.open(prev_path).convert("RGB"), dtype=np.int16)
        if i1.shape == i2.shape:
            diff = np.abs(i1 - i2)
            mad = float(diff.mean())
            maxd = int(diff.max())
        else:
            mad = 9999.0
            maxd = 9999

        h1 = _ahash(out_path)
        h2 = _ahash(prev_path)
        hdist = _hamming(h1, h2)
        # Treat as same when both perceptual and pixel deltas are extremely small.
        if hdist <= 1 and mad <= 0.6 and maxd <= 2:
            return True, str(prev_path)
    except Exception:
        pass
    return False, str(prev_path)


def sample_max_count_and_new_srcs(page, before_srcs: set[str], duration_sec: float = 5.0, poll_sec: float = 0.5) -> tuple[int, list[str]]:
    deadline = time.time() + max(0.5, float(duration_sec))
    max_count = 0
    latest_new: list[str] = []
    while time.time() < deadline:
        srcs = collect_large_image_srcs(page)
        max_count = max(max_count, len(srcs))
        new_srcs = [s for s in srcs if s not in before_srcs]
        if new_srcs:
            latest_new = new_srcs
        time.sleep(max(0.2, float(poll_sec)))
    return max_count, latest_new


def trigger_download_for_generated_src(page, target_src: str) -> bool:
    if not target_src:
        return False
    # Open the generated image first so the per-image download control becomes visible.
    try:
        opened = page.evaluate(
            """(src) => {
              const target = [...document.querySelectorAll('img')].find((el) => (el.getAttribute('src') || '').trim() === src);
              if (!target) return false;
              target.click();
              return true;
            }""",
            target_src,
        )
        if opened:
            try:
                page.wait_for_timeout(400)
            except Exception:
                time.sleep(0.4)
    except Exception:
        pass
    try:
        clicked = page.evaluate(
            """(src) => {
              const target = [...document.querySelectorAll('img')].find((el) => (el.getAttribute('src') || '').trim() === src);
              if (!target) return false;
              let node = target;
              for (let i = 0; i < 18 && node; i++) {
                const btn = node.querySelector('button[aria-label="원본 크기 이미지 다운로드"]');
                if (btn) { btn.click(); return true; }
                node = node.parentElement;
              }
              return false;
            }""",
            target_src,
        )
        if clicked:
            return True
    except Exception:
        pass
    # Do not click global download buttons as fallback. It can download a
    # previously opened image and cause wrong scene-file mapping.
    return False


def save_generated_by_download(
    page,
    out_path: pathlib.Path,
    target_src: str,
    download_dir: pathlib.Path,
    wait_sec: float = 18.0,
) -> bool:
    before = newest_download_file(download_dir)
    before_name = before.name if before else None
    before_m = before.stat().st_mtime if before else 0.0

    if not trigger_download_for_generated_src(page, target_src):
        return False

    deadline = time.time() + wait_sec
    got: pathlib.Path | None = None
    while time.time() < deadline:
        cur = newest_download_file(download_dir)
        if cur and (before_name is None or cur.name != before_name or cur.stat().st_mtime > before_m + 0.0001):
            got = cur
            break
        time.sleep(0.2)
    if got is None:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(got.read_bytes())
    return True


def save_generated_by_src_fetch(page, out_path: pathlib.Path, target_src: str) -> bool:
    if not target_src:
        return False
    try:
        b64 = page.evaluate(
            """(src) => {
              try {
                const imgs = [...document.images].filter((i) =>
                  (i.naturalWidth || 0) >= 256 &&
                  (i.naturalHeight || 0) >= 256 &&
                  (i.clientWidth || 0) >= 32 &&
                  (i.clientHeight || 0) >= 32
                );
                if (!imgs.length) return '';
                let img = null;
                if (typeof src === 'string' && src) {
                  img = imgs.find((i) => (i.getAttribute('src') || '').trim() === src) || null;
                }
                if (!img) img = imgs[imgs.length - 1];
                const c = document.createElement('canvas');
                c.width = img.naturalWidth || img.clientWidth || 0;
                c.height = img.naturalHeight || img.clientHeight || 0;
                const x = c.getContext('2d');
                if (!x || !c.width || !c.height) return '';
                x.drawImage(img, 0, 0);
                const d = c.toDataURL('image/png');
                const i = d.indexOf(',');
                if (i <= 0) return '';
                const raw = d.slice(i + 1);
                if (!raw) return '';
                // Normalize and return base64 only.
                if (raw.startsWith('data:image/')) {
                  const j = raw.indexOf(',');
                  return j > 0 ? raw.slice(j + 1) : '';
                }
                return raw;
              } catch (e) {
                return '';
              }
            }""",
            target_src,
        )
    except Exception:
        return False
    if not b64:
        return False
    try:
        raw = base64.b64decode(str(b64), validate=False)
    except Exception:
        return False
    if not raw:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw)
    return True


def detect_error_text(page) -> str | None:
    try:
        text = str(page.locator("body").inner_text(timeout=500)).lower()
    except Exception:
        return None

    patterns = [
        (
            "quota",
            [
                "limit reached",
                "usage limit",
                "too many requests",
                "try again later",
                "quota",
                "오늘은 이미지를 더 생성할 수 없지만, 웹에서 이미지를 찾을 수 있습니다",
                "오늘은 더 이상 이미지를 생성할 수 없습니다",
                "내일 다시 오시면 더 많은 이미지를 생성해 드리겠습니다",
            ],
        ),
        (
            "blocked",
            [
                "safety",
                "policy",
                "cannot generate",
                "can't generate",
                "생성할 수 없",
                "정책",
                "특정 유형의 이미지를 생성하는 방법은 아직 학습 중이므로",
                "가이드라인에 위배될 수 있습니다",
                "다른 요청이 있으시면 알려주세요",
                "미성년자를 그런 식으로 묘사하는 이미지는 생성할 수 없습니다",
                "대신 도와드릴 수 있는 다른 아이디어",
            ],
        ),
        (
            "unusual_activity",
            [
                "we noticed some unusual activity",
                "please visit the help center for more information",
                "help center for more information",
                "비정상적인 활동이 감지",
            ],
        ),
        (
            "network",
            [
                "network error",
                "connection",
                "오류가 발생",
                "다시 시도",
                "실패 죄송합니다. 문제가 발생했습니다",
                "문제가 발생했습니다",
                "something went wrong",
                "sorry, something went wrong",
            ],
        ),
        (
            "prompt_required",
            [
                "프롬프트를 입력해야 합니다",
                "enter a prompt",
                "please enter a prompt",
                "prompt is required",
            ],
        ),
        ("stopped", ["response stopped", "stopped", "대답이 중지되었습니다", "응답이 중지되었습니다", "중지되었습니다"]),
    ]
    for label, keys in patterns:
        for k in keys:
            if k in text:
                return label
    return None


def is_flow_url(url: str) -> bool:
    u = (url or "").lower()
    return ("labs.google/fx" in u) and ("tools/flow" in u)


def submit_prompt(page) -> None:
    # Default submit via Enter.
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass

    # Flow often requires explicit Generate/Create click.
    try:
        cur = (page.url or "").lower()
    except Exception:
        cur = ""
    if not is_flow_url(cur):
        return

    try:
        page.wait_for_timeout(500)
    except Exception:
        time.sleep(0.5)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)
    except Exception:
        pass

    # Preferred Flow submit: arrow_forward / 만들기 (bottom-right action).
    for sel in [
        "button:has-text('arrow_forward')",
        "button:has-text('arrow_forward') >> text=만들기",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0:
                btn.click(timeout=1200, force=True)
                return
        except Exception:
            pass

    for pat in [r"^generate$", r"생성", r"이미지 생성", r"generate image", r"만들기"]:
        try:
            btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
            if btn.count() > 0:
                txt = ""
                try:
                    txt = (btn.inner_text(timeout=300) or "").strip().lower()
                except Exception:
                    txt = ""
                # Avoid navigation controls such as "Create with Flow" / "New project".
                if any(k in txt for k in ["flow", "project", "프로젝트", "새 프로젝트"]):
                    continue
                if "add_2" in txt and "만들기" in txt:
                    continue
                btn.click(timeout=1200, force=True)
                return
        except Exception:
            pass
    for sel in [
        "button:has-text('Generate')",
        "button:has-text('generate')",
        "button:has-text('생성')",
        "button:has-text('이미지 생성')",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0:
                txt = ""
                try:
                    txt = (btn.inner_text(timeout=300) or "").strip().lower()
                except Exception:
                    txt = ""
                if any(k in txt for k in ["flow", "project", "프로젝트", "새 프로젝트"]):
                    continue
                if "add_2" in txt and "만들기" in txt:
                    continue
                btn.click(timeout=1200, force=True)
                return
        except Exception:
            pass


def pick_browser_page(context, url: str):
    target_host = (urlparse(url).netloc or "").lower()
    page = None
    for p in context.pages:
        cur_url = p.url or ""
        cur_host = (urlparse(cur_url).netloc or "").lower()
        if target_host and cur_host == target_host:
            page = p
            break
        if (not target_host) and ("gemini.google.com" in cur_url):
            page = p
            break
    if page is None:
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
    else:
        cur_url = page.url or ""
        cur_host = (urlparse(cur_url).netloc or "").lower()
        # Important: if we already have a tab on the same host (Flow/Gemini),
        # keep current page state and avoid resetting workspace by re-navigation.
        if not (target_host and cur_host == target_host):
            if url and (url not in cur_url):
                page.goto(url, wait_until="domcontentloaded")
    page.bring_to_front()
    return page


def ensure_flow_entry(page, timeout_sec: float = 18.0) -> bool:
    try:
        cur = (page.url or "").lower()
    except Exception:
        cur = ""
    if not is_flow_url(cur):
        return True

    # If already inside the workspace input area, no-op.
    if has_visible_prompt_input(page):
        return True

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        dismiss_flow_dialogs(page)
        _flow_click_best_effort(page, [r"시작하기", r"get started", r"start"])
        clicked = False
        # Step 1: start a new project when landing shows project list/home.
        for pat in [r"\+\s*새 프로젝트", r"새 프로젝트", r"\+\s*new project", r"new project"]:
            try:
                btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
                if btn.count() > 0:
                    btn.click(timeout=1500, force=True)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            for sel in ["button:has-text('+ 새 프로젝트')", "button:has-text('새 프로젝트')", "button:has-text('+ New project')", "button:has-text('New project')"]:
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        btn.click(timeout=1500, force=True)
                        clicked = True
                        break
                except Exception:
                    pass
        if clicked:
            try:
                page.wait_for_timeout(700)
            except Exception:
                time.sleep(0.7)

        clicked = False
        # Step 2: enter generation workspace.
        for pat in [r"create with flow", r"flow에서 만들기", r"flow로 만들기"]:
            try:
                btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
                if btn.count() > 0:
                    btn.click(timeout=1500, force=True)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            try:
                btn = page.locator("button:has-text('Create with Flow')").first
                if btn.count() > 0:
                    btn.click(timeout=1500, force=True)
                    clicked = True
            except Exception:
                pass
        if not clicked:
            try:
                txt = page.get_by_text(re.compile(r"create with flow", re.I)).first
                if txt.count() > 0:
                    txt.click(timeout=1500, force=True)
                    clicked = True
            except Exception:
                pass
        try:
            page.wait_for_timeout(500)
        except Exception:
            time.sleep(0.5)
        if has_visible_prompt_input(page):
            return True
        if not clicked:
            # nothing to click and no textarea yet
            continue
    return False


def _flow_click_best_effort(page, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
            if btn.count() > 0:
                btn.click(timeout=1200, force=True)
                return True
        except Exception:
            pass
    for pat in patterns:
        try:
            loc = page.get_by_text(re.compile(pat, re.I)).first
            if loc.count() > 0:
                loc.click(timeout=1200, force=True)
                return True
        except Exception:
            pass
    return False


def dismiss_flow_dialogs(page) -> bool:
    """Best-effort close of onboarding/announcement dialogs (e.g. Veo 3.1 Lite)."""
    closed = False
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)
    except Exception:
        pass

    close_patterns = [
        r"닫기",
        r"close",
        r"확인",
        r"계속",
        r"시작하기",
        r"get started",
        r"start",
        r"continue",
        r"got it",
        r"okay",
        r"확인했어요",
    ]
    for pat in close_patterns:
        try:
            btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
            if btn.count() > 0:
                btn.click(timeout=1200, force=True)
                closed = True
                try:
                    page.wait_for_timeout(180)
                except Exception:
                    pass
        except Exception:
            pass

    # Close icon-only dialog buttons.
    for sel in [
        "button[aria-label*='닫기']",
        "button[aria-label*='close' i]",
        "[role='dialog'] button[aria-label*='닫기']",
        "[role='dialog'] button[aria-label*='close' i]",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0:
                btn.click(timeout=1200, force=True)
                closed = True
                try:
                    page.wait_for_timeout(180)
                except Exception:
                    pass
        except Exception:
            pass

    # Veo family intro banners can appear as text-only cards with one CTA.
    if _flow_click_best_effort(page, [r"veo\s*3\.?1\s*lite", r"veo", r"소개", r"announcement"]):
        closed = True
    return closed


def flow_has_retry_conflict(page) -> tuple[bool, dict[str, Any]]:
    """Detect visible retry/failure cards near top viewport that can overlap next submit."""
    try:
        info = page.evaluate(
            """() => {
              function vis(el){
                if (!el) return false;
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) return false;
                return r.bottom > 0 && r.right > 0 && r.left < (window.innerWidth||1) && r.top < (window.innerHeight||1);
              }
              const retryBtns = [...document.querySelectorAll('button')]
                .filter((b) => vis(b))
                .map((b) => ({txt:(b.innerText||'').trim().toLowerCase(), y:(b.getBoundingClientRect().top||0)}))
                .filter((r) => r.txt.includes('다시 시도') || r.txt.includes('retry') || r.txt.includes('try again'));
              const failNodes = [...document.querySelectorAll('*')]
                .filter((n) => vis(n))
                .map((n) => ({txt:((n.innerText||'').trim().toLowerCase()), y:(n.getBoundingClientRect().top||0)}))
                .filter((r) => r.txt === '실패' || r.txt.includes('we noticed some unusual activity'));
              const topRetry = retryBtns.filter((r) => r.y < 700).length;
              const topFail = failNodes.filter((r) => r.y < 700).length;
              return {topRetry, topFail, retryCount: retryBtns.length, failCount: failNodes.length};
            }""",
        )
    except Exception:
        return False, {"error": "probe_failed"}
    top_retry = int(info.get("topRetry") or 0)
    top_fail = int(info.get("topFail") or 0)
    conflict = top_retry > 0 and top_fail > 0
    return conflict, info


def ensure_flow_controls(page, timeout_sec: float = 12.0) -> bool:
    """Check Flow control area before generation and try to set defaults:
    model (Nano Banana 2), image mode, 16:9 ratio, 1 output.
    """
    try:
        cur = (page.url or "").lower()
    except Exception:
        cur = ""
    if not is_flow_url(cur):
        return True

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        dismiss_flow_dialogs(page)
        # Re-try landing transitions if workspace controls are not visible yet.
        _flow_click_best_effort(page, [r"\+\s*새 프로젝트", r"새 프로젝트", r"\+\s*new project", r"new project"])
        _flow_click_best_effort(page, [r"create with flow", r"flow에서 만들기", r"flow로 만들기"])

        try:
            body = str(page.locator("body").inner_text(timeout=800))
        except Exception:
            body = ""
        body_l = body.lower()
        has_prompt_box = has_visible_prompt_input(page)

        has_media = any(k in body_l for k in ["이미지", "동영상", "image", "video"])
        has_ratio = any(k in body_l for k in ["비율", "aspect", "16:9", "9:16", "1:1", "4:3"])
        has_count = any(k in body_l for k in ["출력", "개수", "outputs", "variations", "1개", "x1"])
        has_model = any(k in body_l for k in ["nano banana 2", "model", "모델"])

        # Read compact control button text (often: "Nano Banana 2 / crop_16_9 / x2").
        btn_blob = ""
        try:
            parts = []
            for b in page.get_by_role("button").all()[:80]:
                try:
                    t = str(b.inner_text() or "").strip()
                except Exception:
                    t = ""
                if t:
                    parts.append(t.lower())
            btn_blob = " | ".join(parts)
        except Exception:
            btn_blob = ""
        has_model = has_model or ("nano banana 2" in btn_blob)
        has_ratio = has_ratio or ("16:9" in btn_blob or "crop_16_9" in btn_blob)
        has_count = has_count or ("x1" in btn_blob or "1개" in btn_blob or "1 output" in btn_blob)

        # Best-effort defaults for this pipeline.
        # Open compact control hub first (if present), then pick values.
        _flow_click_best_effort(page, [r"nano banana 2", r"nano\s+banana", r"🍌", r"crop_16_9", r"x[1-4]"])
        _flow_click_best_effort(page, [r"nano banana 2", r"nano\s+banana"])
        _flow_click_best_effort(page, [r"^이미지$", r"^image$"])
        _flow_click_best_effort(page, [r"16:9", r"16\s*[x×/]\s*9"])
        _flow_click_best_effort(page, [r"^1개$", r"^x1$", r"^1 output$", r"output\s*1", r"1개 생성"])

        try:
            page.wait_for_timeout(350)
        except Exception:
            time.sleep(0.35)

        # In some Flow builds, the controls are icon-only / virtualized and
        # plain body-text detection misses them. If prompt input is present,
        # proceed after best-effort default clicks.
        if has_prompt_box:
            return True
        if has_model and has_media and has_ratio and has_count:
            return True
    return False


def run_character_precheck(story_id: str, start_scene: int, end_scene: int | None) -> int:
    cmd = [
        sys.executable,
        "skills/make_vrew/scripts/check_gemini_character_consistency.py",
        "--story-id",
        story_id,
        "--start-scene",
        str(start_scene),
        "--strict",
    ]
    if end_scene is not None:
        cmd.extend(["--end-scene", str(end_scene)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip())
        print("FAIL: character consistency precheck failed. Fix prompts before generation.")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini CDP batch clip generator with error detection")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    ap.add_argument("--url", default="https://gemini.google.com/app")
    ap.add_argument("--start-scene", type=int, default=1)
    ap.add_argument("--end-scene", type=int, default=None)
    ap.add_argument("--timeout-sec", type=int, default=90)
    ap.add_argument("--cooldown-sec", type=float, default=1.2)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--skip-character-precheck", action="store_true")
    ap.add_argument("--require-manual-confirm", action="store_true")
    ap.add_argument("--idle-timeout-sec", type=float, default=45.0)
    ap.add_argument("--idle-stable-sec", type=float, default=2.0)
    ap.add_argument("--idle-poll-sec", type=float, default=0.5)
    ap.add_argument("--gen-poll-sec", type=float, default=1.0, help="Polling interval while waiting generation state transitions.")
    ap.add_argument("--min-post-submit-sec", type=float, default=25.0, help="Minimum seconds to wait after submit before allowing completion.")
    ap.add_argument("--start-fallback-sec", type=float, default=15.0, help="Fallback seconds to accept start via image deltas when running signal is absent.")
    ap.add_argument("--allow-retry-submit", action="store_true", help="Allow one retry submit on early stopped/blocked. Default is strict single submit.")
    ap.add_argument("--min-card-match-score", type=float, default=0.45, help="Minimum prompt-card text match score required before download.")
    ap.add_argument("--max-failure-retries", type=int, default=2, help="Automatic retries per scene for retryable failures.")
    ap.add_argument("--retry-wait-sec", type=float, default=8.0, help="Base wait seconds before retrying a retryable failure.")
    ap.add_argument("--pre-submit-guard-timeout-sec", type=float, default=12.0, help="Seconds to wait for retry/failure conflict to clear before submit.")
    ap.add_argument("--state-debug", action="store_true")
    ap.add_argument("--ensure-image-mode", action="store_true", default=True)
    ap.add_argument("--no-ensure-image-mode", dest="ensure_image_mode", action="store_false")
    ap.add_argument(
        "--blocked-fallback-suffix",
        default="daytime neutral composition, non-violent, no horror elements, calm atmosphere, simple scene layout",
        help="Suffix used once when blocked-policy message is detected.",
    )
    ap.add_argument(
        "--prompt-suffix",
        default="",
        help="Extra prompt text appended to every scene prompt (e.g., brighter lighting guidance).",
    )
    ap.add_argument(
        "--download-dir",
        default="~/Downloads",
        help="Directory where Gemini saves downloaded original images.",
    )
    ap.add_argument(
        "--verify-latest-reuse-only",
        action="store_true",
        help="Do not submit a new prompt. Verify latest visible card via '프롬프트 재사용' against scene prompt, then save only when matched.",
    )
    args = ap.parse_args()

    project_json = pathlib.Path("work") / args.story_id / "out" / "project.json"
    clips_dir = pathlib.Path("work") / args.story_id / "clips"
    logs_dir = pathlib.Path("work") / args.story_id / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_path = logs_dir / f"gemini_batch_{int(time.time())}.json"
    download_dir = pathlib.Path(args.download_dir).expanduser()
    download_dir.mkdir(parents=True, exist_ok=True)

    if not project_json.exists():
        print(f"FAIL: missing {project_json}")
        return 2

    if not args.skip_character_precheck:
        rc = run_character_precheck(args.story_id, args.start_scene, args.end_scene)
        if rc != 0:
            return 2

    jobs = load_scene_prompts(project_json, args.start_scene, args.end_scene)
    if not jobs:
        print("FAIL: no scene prompts found")
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("FAIL: playwright not installed")
        return 2

    results: list[dict[str, Any]] = []
    stopped_reason = None

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_endpoint)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = pick_browser_page(context, args.url)
        _ = ensure_flow_entry(page)
        if not ensure_flow_controls(page):
            print("FAIL: flow_controls_not_ready (model, image/video, ratio, outputs controls not detected)")
            report = {
                "story_id": args.story_id,
                "start_scene": args.start_scene,
                "end_scene": args.end_scene,
                "stopped_reason": "flow_controls_not_ready",
                "total_jobs": len(jobs),
                "results": [],
            }
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1

        if args.require_manual_confirm:
            print("Gemini 로그인/준비 상태 확인 후 Enter")
            input("> ")
        else:
            print("INFO: manual confirm skipped; continuing automatically.")

        for sid, prompt in jobs:
            out_path = clips_dir / f"{sid:03d}.png"
            if out_path.exists() and not args.overwrite:
                results.append({"scene": sid, "status": "skipped_exists", "path": str(out_path)})
                continue

            page.bring_to_front()
            dismiss_flow_dialogs(page)
            if args.ensure_image_mode:
                _ = ensure_image_mode(page)

            if args.verify_latest_reuse_only:
                final_prompt = merge_prompt_suffix(prompt, args.prompt_suffix)
                srcs = collect_large_image_srcs(page)
                if not srcs:
                    results.append({"scene": sid, "status": "no_visible_image_for_reuse_check"})
                    stopped_reason = "no_visible_image_for_reuse_check"
                    break
                target_src = srcs[-1]
                dom_card = card_text_for_image_src(page, target_src)
                dom_score = prompt_card_match_score(final_prompt, dom_card)
                verify_source = "dom_card_text"
                verified_text = dom_card
                verify_score = dom_score
                reused = reused_prompt_text_for_image_src(page, target_src)
                reuse_score = prompt_card_match_score(final_prompt, reused) if reused else 0.0
                if reuse_score > verify_score:
                    verify_source = "reuse_icon_prompt"
                    verified_text = reused
                    verify_score = reuse_score

                if verify_score < float(args.min_card_match_score):
                    results.append(
                        {
                            "scene": sid,
                            "status": "reuse_prompt_unavailable" if not reused and not dom_card else "reuse_prompt_mismatch",
                            "match_score": round(float(verify_score), 4),
                            "min_required": float(args.min_card_match_score),
                            "target_src_preview": target_src[:140],
                            "verify_source": verify_source,
                            "dom_card_preview": (dom_card or "")[:200],
                            "reused_prompt_preview": (reused or "")[:200],
                        }
                    )
                    stopped_reason = "reuse_prompt_unavailable" if not reused and not dom_card else "reuse_prompt_mismatch"
                    break

                saved = save_generated_by_src_fetch(
                    page=page,
                    out_path=out_path,
                    target_src=target_src,
                )
                if not saved:
                    saved = save_generated_by_download(
                        page=page,
                        out_path=out_path,
                        target_src=target_src,
                        download_dir=download_dir,
                    )
                if not saved:
                    saved = save_newest_generated_image(
                        page=page,
                        out_path=out_path,
                        new_srcs=[target_src],
                    )
                if not saved:
                    results.append({"scene": sid, "status": "save_failed_download", "path": str(out_path)})
                    stopped_reason = "save_failed_download"
                    break

                is_dup_prev, prev_path = same_as_prev_scene(clips_dir=clips_dir, sid=sid, out_path=out_path)
                if is_dup_prev:
                    results.append(
                        {
                            "scene": sid,
                            "status": "duplicate_as_previous_scene",
                            "path": str(out_path),
                            "previous_scene_path": prev_path,
                        }
                    )
                    stopped_reason = "duplicate_as_previous_scene"
                    break

                results.append(
                    {
                        "scene": sid,
                        "status": "ok_reuse_verified",
                        "path": str(out_path),
                        "match_score": round(float(verify_score), 4),
                        "verify_source": verify_source,
                        "verified_prompt_preview": (verified_text or "")[:200],
                    }
                )
                time.sleep(max(0.0, args.cooldown_sec))
                continue

            idle_ok, idle_state = wait_until_idle(
                page=page,
                timeout_sec=args.idle_timeout_sec,
                stable_sec=args.idle_stable_sec,
                poll_sec=args.idle_poll_sec,
            )
            if args.state_debug:
                print(f"STATE(before scene={sid}): {json.dumps(idle_state, ensure_ascii=False)}")
            if not idle_ok:
                results.append({"scene": sid, "status": "precheck_not_idle", "state": idle_state})
                stopped_reason = "precheck_not_idle"
                break
            if bool(idle_state.get("has_stopped_banner")):
                try:
                    page.keyboard.press("Escape")
                    time.sleep(0.4)
                except Exception:
                    pass

            # Hard guard: do not submit next scene while top-level retry/failure card
            # is visible, which can overlap with new generation and corrupt mapping.
            guard_deadline = time.time() + max(1.0, float(args.pre_submit_guard_timeout_sec))
            guard_conflict = False
            guard_info: dict[str, Any] = {}
            while time.time() < guard_deadline:
                guard_conflict, guard_info = flow_has_retry_conflict(page)
                if not guard_conflict:
                    break
                time.sleep(max(0.2, args.gen_poll_sec))
            if guard_conflict:
                results.append(
                    {
                        "scene": sid,
                        "status": "pre_submit_retry_conflict",
                        "retry_probe": guard_info,
                    }
                )
                stopped_reason = "pre_submit_retry_conflict"
                break

            # Per-scene hard refresh before typing a new prompt to reduce stale UI state.
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
            except Exception:
                try:
                    page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
            dismiss_flow_dialogs(page)
            if not ensure_flow_controls(page):
                results.append({"scene": sid, "status": "flow_controls_not_ready_after_refresh"})
                stopped_reason = "flow_controls_not_ready_after_refresh"
                break
            if args.ensure_image_mode:
                _ = ensure_image_mode(page)
            idle_ok2, idle_state2 = wait_until_idle(
                page=page,
                timeout_sec=args.idle_timeout_sec,
                stable_sec=args.idle_stable_sec,
                poll_sec=args.idle_poll_sec,
            )
            if args.state_debug:
                print(f"STATE(after refresh scene={sid}): {json.dumps(idle_state2, ensure_ascii=False)}")
            if not idle_ok2:
                results.append({"scene": sid, "status": "not_idle_after_refresh", "state": idle_state2})
                stopped_reason = "not_idle_after_refresh"
                break

            final_prompt = merge_prompt_suffix(prompt, args.prompt_suffix)
            prompt_set_ok = set_prompt(page, final_prompt)
            if not prompt_set_ok:
                results.append({"scene": sid, "status": "prompt_input_not_found"})
                stopped_reason = "prompt_input_not_found"
                break
            if not prompt_text_matches(page, final_prompt):
                results.append({"scene": sid, "status": "prompt_not_reflected_after_input"})
                stopped_reason = "prompt_not_reflected_after_input"
                break

            before = count_large_images(page)
            before_srcs = set(collect_large_image_srcs(page))
            before_state = collect_state(page)
            before_last_src_hash = str(before_state.get("last_src_hash") or "")
            submit_prompt(page)
            submit_ts = time.time()
            retryable_fail_retries = 0

            ok = False
            err = None
            detected_new_srcs: list[str] = []
            count_increase_seen = False
            card_match_seen = False
            card_match_best = 0.0
            deadline = time.time() + args.timeout_sec
            stable_ready_count = 0
            last_settle_hash = ""
            seen_running_after_submit = False
            started = False
            delta_seen = False
            hash_delta_seen = False
            idle_after_start_count = 0
            retried_after_stopped = False
            retried_after_blocked = False
            retried_after_prompt_required = False
            last_now_srcs: list[str] = []
            while time.time() < deadline:
                st = collect_state(page)
                if bool(st.get("has_running_banner")):
                    seen_running_after_submit = True
                now_srcs = collect_large_image_srcs(page)
                last_now_srcs = now_srcs
                now_count = len(now_srcs)
                new_srcs = [s for s in now_srcs if s not in before_srcs]
                cur_hash = str(st.get("last_src_hash") or "")
                hash_changed = bool(cur_hash and cur_hash != before_last_src_hash)
                if hash_changed:
                    hash_delta_seen = True
                count_changed = bool(now_count > int(before))
                if count_changed:
                    count_increase_seen = True
                # Flow sometimes updates existing cards in place without introducing
                # a brand-new src URL; accept count/hash deltas too.
                image_delta = bool(new_srcs or hash_changed or count_changed)
                if image_delta:
                    delta_seen = True
                if new_srcs or hash_changed or count_changed:
                    if new_srcs:
                        detected_new_srcs = new_srcs
                    running = bool(st.get("has_running_banner"))
                    elapsed = time.time() - submit_ts
                    # Some Flow builds never expose running/stop signals even when
                    # generation is actually in progress. Allow a delayed fallback
                    # start condition when image deltas are observed.
                    started_ok = seen_running_after_submit or (
                        elapsed >= args.start_fallback_sec and (count_changed or hash_changed or bool(new_srcs))
                    )
                    # Require the generated image to settle before moving on.
                    if running or not cur_hash or not started_ok or cur_hash == before_last_src_hash:
                        stable_ready_count = 0
                        last_settle_hash = cur_hash
                    else:
                        if cur_hash == last_settle_hash:
                            stable_ready_count += 1
                        else:
                            stable_ready_count = 1
                            last_settle_hash = cur_hash
                        if stable_ready_count >= 3:
                            ok = True
                            break
                _, cur_card_score, _ = best_card_match_anywhere(page, final_prompt)
                if cur_card_score > card_match_best:
                    card_match_best = cur_card_score
                if cur_card_score >= float(args.min_card_match_score):
                    card_match_seen = True
                err = detect_error_text(page)
                if err == "prompt_required" and prompt_text_matches(page, final_prompt):
                    # Ignore stale warning if the prompt is actually present.
                    err = None
                if err == "stopped" and (time.time() - submit_ts) < 8.0:
                    err = None
                if err == "blocked" and (time.time() - submit_ts) < 8.0:
                    err = None
                if err == "blocked" and not seen_running_after_submit:
                    err = None
                # Flow often shows transient "문제가 발생했습니다" while image still completes.
                if err == "network":
                    elapsed = time.time() - submit_ts
                    if seen_running_after_submit or elapsed < 20.0 or delta_seen:
                        err = None
                # Only retry stopped when generation did not actually start.
                if (
                    args.allow_retry_submit
                    and err == "stopped"
                    and not retried_after_stopped
                    and not seen_running_after_submit
                ):
                    # Retry once on stopped answer before failing the scene.
                    retried_after_stopped = True
                    # Ensure page returned to idle before retrying Enter.
                    wait_until_idle(
                        page=page,
                        timeout_sec=min(12.0, args.idle_timeout_sec),
                        stable_sec=min(1.0, args.idle_stable_sec),
                        poll_sec=args.idle_poll_sec,
                    )
                    submit_prompt(page)
                    time.sleep(1.2)
                    continue
                if err == "stopped":
                    # Strict-serial default: do not re-submit automatically.
                    if not args.allow_retry_submit:
                        if delta_seen:
                            err = None
                        else:
                            # keep observing briefly; many stopped toasts are transient
                            time.sleep(max(0.2, args.gen_poll_sec))
                            continue
                if args.allow_retry_submit and err == "blocked" and not retried_after_blocked:
                    retried_after_blocked = True
                    fallback_prompt = merge_prompt_suffix(final_prompt, args.blocked_fallback_suffix)
                    if set_prompt(page, fallback_prompt):
                        before_srcs = set(collect_large_image_srcs(page))
                        before_last_src_hash = str((collect_state(page).get("last_src_hash") or ""))
                        submit_prompt(page)
                        submit_ts = time.time()
                        stable_ready_count = 0
                        last_settle_hash = ""
                        seen_running_after_submit = False
                        time.sleep(1.0)
                        continue
                if err in {"quota", "blocked"}:
                    break
                if err == "unusual_activity":
                    if retryable_fail_retries < max(0, int(args.max_failure_retries)):
                        retryable_fail_retries += 1
                        time.sleep(max(0.5, float(args.retry_wait_sec) * retryable_fail_retries))
                        wait_until_idle(
                            page=page,
                            timeout_sec=min(20.0, args.idle_timeout_sec),
                            stable_sec=max(1.0, min(2.0, args.idle_stable_sec)),
                            poll_sec=args.idle_poll_sec,
                        )
                        if not set_prompt(page, final_prompt):
                            err = "prompt_input_not_found"
                            break
                        before = count_large_images(page)
                        before_srcs = set(collect_large_image_srcs(page))
                        before_state = collect_state(page)
                        before_last_src_hash = str(before_state.get("last_src_hash") or "")
                        submit_prompt(page)
                        submit_ts = time.time()
                        stable_ready_count = 0
                        last_settle_hash = ""
                        seen_running_after_submit = False
                        started = False
                        delta_seen = False
                        hash_delta_seen = False
                        idle_after_start_count = 0
                        detected_new_srcs = []
                        last_now_srcs = []
                        err = None
                        continue
                    break
                if err == "prompt_required":
                    # Do not auto-retry submit here; repeated retries can trigger
                    # duplicate generations in Flow. Let operator verify and rerun.
                    results.append({"scene": sid, "status": "prompt_required_manual_check"})
                    stopped_reason = "prompt_required_manual_check"
                    break

                # Strict serial gating for Flow/Gemini:
                # 1) wait for generation start signal after submit
                # 2) then wait for idle recovery (generation finished)
                if has_generation_start_signal(st):
                    seen_running_after_submit = True
                if seen_running_after_submit or image_delta:
                    started = True

                if started and is_idle_state(st):
                    idle_after_start_count += 1
                else:
                    idle_after_start_count = 0

                # Fast completion (<15s) is accepted as soon as start+delta+stable-idle are observed.
                if started and delta_seen and idle_after_start_count >= 2:
                    if (time.time() - submit_ts) < float(args.min_post_submit_sec):
                        time.sleep(max(0.2, args.gen_poll_sec))
                        continue
                    if not detected_new_srcs and now_srcs:
                        detected_new_srcs = [now_srcs[-1]]
                    ok = bool(detected_new_srcs or now_srcs)
                    if ok:
                        break
                time.sleep(max(0.2, args.gen_poll_sec))

            if ok:
                # Re-check after a short idle wait to avoid early decision while
                # Flow is still finalizing generation.
                wait_until_idle(
                    page=page,
                    timeout_sec=min(20.0, args.idle_timeout_sec),
                    stable_sec=max(1.0, min(2.0, args.idle_stable_sec)),
                    poll_sec=args.idle_poll_sec,
                )
                now_srcs_post = collect_large_image_srcs(page)
                if len(now_srcs_post) > int(before):
                    count_increase_seen = True
                if not detected_new_srcs:
                    detected_new_srcs = [s for s in now_srcs_post if s not in before_srcs]
                # Stabilize against transient DOM reflow drops (e.g. 27->26->27).
                max_count_post, sampled_new_srcs = sample_max_count_and_new_srcs(
                    page=page,
                    before_srcs=before_srcs,
                    duration_sec=5.0,
                    poll_sec=max(0.2, args.gen_poll_sec),
                )
                if max_count_post > int(before):
                    count_increase_seen = True
                if (not detected_new_srcs) and sampled_new_srcs:
                    detected_new_srcs = sampled_new_srcs
                st_post = collect_state(page)
                if has_generation_start_signal(st_post):
                    results.append(
                        {
                            "scene": sid,
                            "status": "still_generating_after_ok_probe",
                            "state": st_post,
                        }
                    )
                    stopped_reason = "still_generating_after_ok_probe"
                    break
                _, post_card_score, _ = best_card_match_anywhere(page, final_prompt)
                if post_card_score > card_match_best:
                    card_match_best = post_card_score
                if post_card_score >= float(args.min_card_match_score):
                    card_match_seen = True

                # Primary rule: a prompt-matching card must appear after submit.
                if not card_match_seen:
                    results.append(
                        {
                            "scene": sid,
                            "status": "no_prompt_card_match_after_submit",
                            "before_count": int(before),
                            "after_count": len(now_srcs_post),
                            "max_count_post": int(max_count_post),
                            "best_card_score": round(float(card_match_best), 4),
                        }
                    )
                    stopped_reason = "no_prompt_card_match_after_submit"
                    break
                # Safety guard: if only image count changed without src/hash delta,
                # target image can be ambiguous and may cause repeated wrong saves.
                if (not detected_new_srcs) and (not hash_delta_seen):
                    results.append(
                        {
                            "scene": sid,
                            "status": "ambiguous_target_no_src_or_hash_delta",
                            "before_count": int(before),
                            "after_count": len(last_now_srcs),
                        }
                    )
                    stopped_reason = "ambiguous_target_no_src_or_hash_delta"
                    break

                fallback_target = (detected_new_srcs[-1] if detected_new_srcs else (last_now_srcs[-1] if last_now_srcs else ""))
                target_src, match_score, card_txt = choose_target_src_by_card_match(
                    page=page,
                    prompt=final_prompt,
                    preferred_srcs=(detected_new_srcs or ([fallback_target] if fallback_target else [])),
                )
                if not target_src or not card_txt:
                    results.append(
                        {
                            "scene": sid,
                            "status": "card_text_unavailable_before_download",
                            "target_src_preview": fallback_target[:140],
                        }
                    )
                    stopped_reason = "card_text_unavailable_before_download"
                    break
                if match_score < float(args.min_card_match_score):
                    results.append(
                        {
                            "scene": sid,
                            "status": "card_text_mismatch_before_download",
                            "match_score": round(match_score, 4),
                            "min_required": float(args.min_card_match_score),
                            "target_src_preview": target_src[:140],
                        }
                    )
                    stopped_reason = "card_text_mismatch_before_download"
                    break
                # Prefer src-bound fetch first for stable scene-to-image mapping.
                saved = save_generated_by_src_fetch(
                    page=page,
                    out_path=out_path,
                    target_src=target_src,
                )
                if not saved:
                    saved = save_generated_by_download(
                        page=page,
                        out_path=out_path,
                        target_src=target_src,
                        download_dir=download_dir,
                    )
                if not saved:
                    # Flow UI often blocks direct download hooks; allow visual fallback capture.
                    saved = save_newest_generated_image(
                        page=page,
                        out_path=out_path,
                        new_srcs=detected_new_srcs,
                    )
                if saved:
                    is_dup_prev, prev_path = same_as_prev_scene(clips_dir=clips_dir, sid=sid, out_path=out_path)
                    if is_dup_prev:
                        results.append(
                            {
                                "scene": sid,
                                "status": "duplicate_as_previous_scene",
                                "path": str(out_path),
                                "previous_scene_path": prev_path,
                            }
                        )
                        stopped_reason = "duplicate_as_previous_scene"
                        break
                    results.append({"scene": sid, "status": "ok", "path": str(out_path)})
                else:
                    results.append({"scene": sid, "status": "save_failed_download", "path": str(out_path)})
                # Hard guard: never proceed while previous generation might still be active.
                wait_until_idle(
                    page=page,
                    timeout_sec=min(20.0, args.idle_timeout_sec),
                    stable_sec=max(1.5, args.idle_stable_sec),
                    poll_sec=args.idle_poll_sec,
                )
                time.sleep(max(0.0, args.cooldown_sec))
                continue

            if err:
                # If network toast appeared but an image exists, prefer image save path.
                if err == "network":
                    try:
                        cur_url = (page.url or "").lower()
                    except Exception:
                        cur_url = ""
                    if is_flow_url(cur_url):
                        flow_srcs = collect_large_image_srcs(page)
                        if flow_srcs:
                            latest_src = flow_srcs[-1]
                            saved = save_generated_by_src_fetch(
                                page=page,
                                out_path=out_path,
                                target_src=latest_src,
                            )
                            if not saved:
                                saved = save_newest_generated_image(
                                    page=page,
                                    out_path=out_path,
                                    new_srcs=[latest_src],
                                )
                            if saved:
                                is_dup_prev, prev_path = same_as_prev_scene(clips_dir=clips_dir, sid=sid, out_path=out_path)
                                if is_dup_prev:
                                    results.append(
                                        {
                                            "scene": sid,
                                            "status": "duplicate_as_previous_scene",
                                            "path": str(out_path),
                                            "previous_scene_path": prev_path,
                                        }
                                    )
                                    stopped_reason = "duplicate_as_previous_scene"
                                    break
                                results.append({"scene": sid, "status": "ok_flow_network_recovered", "path": str(out_path)})
                                time.sleep(max(0.0, args.cooldown_sec))
                                continue
                results.append({"scene": sid, "status": f"error_{err}"})
                stopped_reason = f"error_{err}"
                break

            # Flow-specific fallback: generation may complete without a detectable
            # "new src" signal. If any large image is present, save the latest one.
            try:
                cur_url = (page.url or "").lower()
            except Exception:
                cur_url = ""
            if is_flow_url(cur_url):
                flow_srcs = collect_large_image_srcs(page)
                if flow_srcs:
                    latest_src = flow_srcs[-1]
                    saved = save_generated_by_src_fetch(
                        page=page,
                        out_path=out_path,
                        target_src=latest_src,
                    )
                    if not saved:
                        saved = save_newest_generated_image(
                            page=page,
                            out_path=out_path,
                            new_srcs=[latest_src],
                        )
                    if saved:
                        is_dup_prev, prev_path = same_as_prev_scene(clips_dir=clips_dir, sid=sid, out_path=out_path)
                        if is_dup_prev:
                            results.append(
                                {
                                    "scene": sid,
                                    "status": "duplicate_as_previous_scene",
                                    "path": str(out_path),
                                    "previous_scene_path": prev_path,
                                }
                            )
                            stopped_reason = "duplicate_as_previous_scene"
                            break
                        results.append({"scene": sid, "status": "ok_flow_timeout_fallback", "path": str(out_path)})
                        time.sleep(max(0.0, args.cooldown_sec))
                        continue

            results.append({"scene": sid, "status": "timeout_no_image"})
            stopped_reason = "timeout_no_image"
            break

    report = {
        "story_id": args.story_id,
        "start_scene": args.start_scene,
        "end_scene": args.end_scene,
        "stopped_reason": stopped_reason,
        "total_jobs": len(jobs),
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ok_count = sum(1 for r in results if r.get("status") == "ok")
    print(f"DONE: ok={ok_count}, processed={len(results)}, report={report_path}")
    if stopped_reason:
        print(f"STOPPED: {stopped_reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
