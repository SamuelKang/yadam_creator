from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


DOWNLOAD_GLOB = "Gemini_Generated_Image*"


def load_scene_prompts(project_json: Path, max_scene: int | None) -> list[dict[str, Any]]:
    obj = json.loads(project_json.read_text(encoding="utf-8"))
    scenes = obj.get("scenes", [])
    out: list[dict[str, Any]] = []
    for i, s in enumerate(scenes, start=1):
        if max_scene and i > max_scene:
            break
        prompt = (s.get("image", {}).get("prompt_used") or s.get("llm_clip_prompt") or "").strip()
        if not prompt:
            continue
        out.append(
            {
                "scene": i,
                "prompt": prompt,
                "prompt_hash": hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10],
            }
        )
    return out


def newest_download(download_dir: Path) -> Path | None:
    files = sorted(download_dir.glob(DOWNLOAD_GLOB), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def pick_best_page(browser):
    best = None
    best_score = -1
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "gemini.google.com" not in (pg.url or ""):
                continue
            try:
                score = pg.get_by_role("button", name="원본 크기 이미지 다운로드").count()
            except Exception:
                score = 0
            if score > best_score:
                best_score = score
                best = pg
    return best


def collect_visible_cards(page) -> list[dict[str, Any]]:
    js = r"""() => {
      const btnSel = 'button[aria-label="원본 크기 이미지 다운로드"]';
      const btns = [...document.querySelectorAll(btnSel)];
      const rows = [];

      function clean(t) { return (t || '').replace(/\s+/g, ' ').trim(); }

      for (let i = 0; i < btns.length; i++) {
        const b = btns[i];
        const br = b.getBoundingClientRect();
        if (!br || br.bottom < 0 || br.top > innerHeight) continue;

        let node = b;
        let txt = '';
        let img = null;
        for (let up = 0; up < 14 && node; up++) {
          node = node.parentElement;
          if (!node) break;
          const t = clean(node.innerText || '');
          if (!txt && (t.includes('Primary subjects:') || t.includes('Visible action:') || t.includes('Ghibli-inspired'))) {
            txt = t;
          }
          if (!img) {
            const cand = node.querySelector('img');
            if (cand) {
              const ir = cand.getBoundingClientRect();
              if (ir && ir.width >= 120 && ir.height >= 120) img = cand;
            }
          }
          if (txt && img) break;
        }

        const ir = img ? img.getBoundingClientRect() : null;
        const x = ir ? Math.max(10, ir.left + ir.width * 0.5) : Math.max(10, br.left - 120);
        const y = ir ? Math.max(10, ir.top + ir.height * 0.5) : Math.max(10, br.top - 120);
        const key = `${Math.round(br.top)}|${Math.round(br.left)}|${(txt || '').slice(0,80)}`;

        rows.push({
          btn_index: i,
          key,
          y: br.top,
          x_click: x,
          y_click: y,
          text: txt || ''
        });
      }
      rows.sort((a,b) => a.y - b.y);
      return rows;
    }"""
    return page.evaluate(js) or []


def best_scene_match(card_text: str, scenes: list[dict[str, Any]], used: set[int]) -> tuple[int | None, float]:
    if not card_text:
        return None, 0.0
    card_norm = " ".join(card_text.split())
    best_scene = None
    best_score = 0.0
    for s in scenes:
        sid = int(s["scene"])
        if sid in used:
            continue
        prm = " ".join(str(s["prompt"]).split())
        ratio = difflib.SequenceMatcher(None, card_norm[:900], prm[:900]).ratio()
        bonus = 0.0
        if card_norm[:120] and card_norm[:120] in prm:
            bonus += 0.2
        if "Primary subjects:" in card_norm and "Primary subjects:" in prm:
            bonus += 0.05
        if "Visible action:" in card_norm and "Visible action:" in prm:
            bonus += 0.05
        score = min(1.0, ratio + bonus)
        if score > best_score:
            best_score = score
            best_scene = sid
    return best_scene, best_score


def extract_scene_order_from_body(
    page, scenes: list[dict[str, Any]], max_count: int
) -> list[int]:
    try:
        body_text = page.evaluate(
            "() => document.body ? (document.body.innerText || '') : ''"
        )
    except Exception:
        body_text = ""
    if not body_text:
        return []

    hits: list[tuple[int, int]] = []
    for s in scenes:
        sid = int(s["scene"])
        prm = str(s["prompt"])
        needle = prm[:120]
        if not needle:
            continue
        pos = body_text.find(needle)
        if pos >= 0:
            hits.append((pos, sid))

    hits.sort(key=lambda x: x[0])
    out: list[int] = []
    seen: set[int] = set()
    for _, sid in hits:
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
        if len(out) >= max_count:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--max-scene", type=int, default=40)
    ap.add_argument("--min-score", type=float, default=0.55)
    ap.add_argument("--max-save", type=int, default=20)
    args = ap.parse_args()

    base = Path("work") / args.story_id
    project_json = base / "out" / "project.json"
    out_dir = base / "clips_original"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = base / "out"
    log_dir.mkdir(parents=True, exist_ok=True)
    download_dir = Path.home() / "Downloads"

    scenes = load_scene_prompts(project_json, args.max_scene)
    used_scenes = {int(p.stem) for p in out_dir.glob("*.png") if p.stem.isdigit()}
    seen_hash = {md5_file(p) for p in out_dir.glob("*.png")}
    seen_cards: set[str] = set()

    run_log: dict[str, Any] = {
        "ts": int(time.time()),
        "story_id": args.story_id,
        "max_scene": args.max_scene,
        "min_score": args.min_score,
        "rows": [],
    }

    saved = 0
    idle_rounds = 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = pick_best_page(browser)
        if not page:
            print("FAIL:no_gemini_page")
            return 2
        page.bring_to_front()
        time.sleep(0.4)
        # start from feed mode
        try:
            page.keyboard.press("Escape")
            time.sleep(0.2)
        except Exception:
            pass
        # move near top so card order starts from early scenes
        for _ in range(8):
            page.mouse.wheel(0, -9000)
            time.sleep(0.08)

        while saved < args.max_save and idle_rounds < 10:
            cards = collect_visible_cards(page)
            fallback_order = extract_scene_order_from_body(page, scenes, len(cards))
            progressed = False

            for i, card in enumerate(cards):
                key = str(card.get("key", ""))
                if key in seen_cards:
                    continue
                seen_cards.add(key)

                card_text = str(card.get("text", ""))
                scene_id, score = best_scene_match(card_text, scenes, used_scenes)
                if (
                    (not scene_id or score < args.min_score)
                    and i < len(fallback_order)
                    and fallback_order[i] not in used_scenes
                ):
                    scene_id = fallback_order[i]
                    score = max(score, 0.62)
                row: dict[str, Any] = {
                    "btn_index": int(card["btn_index"]),
                    "scene": scene_id,
                    "score": round(score, 4),
                    "status": "",
                    "text_preview": card_text[:180],
                }

                if not scene_id or score < args.min_score:
                    row["status"] = "unmatched"
                    run_log["rows"].append(row)
                    continue

                target = out_dir / f"{scene_id:03d}.png"
                if target.exists():
                    row["status"] = "already_exists"
                    used_scenes.add(scene_id)
                    run_log["rows"].append(row)
                    continue

                before = newest_download(download_dir)
                before_name = before.name if before else None
                before_m = before.stat().st_mtime if before else 0.0

                try:
                    page.mouse.click(float(card["x_click"]), float(card["y_click"]))
                    time.sleep(0.5)
                except Exception as e:
                    row["status"] = f"open_fail:{str(e)[:80]}"
                    run_log["rows"].append(row)
                    continue

                try:
                    btn = page.get_by_role("button", name="원본 크기 이미지 다운로드").first
                    if btn.count() == 0:
                        row["status"] = "no_download_button"
                        run_log["rows"].append(row)
                        try:
                            page.keyboard.press("Escape")
                        except Exception:
                            pass
                        continue
                    btn.click(timeout=2500)
                except Exception as e:
                    row["status"] = f"click_fail:{str(e)[:80]}"
                    run_log["rows"].append(row)
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    continue

                got = None
                for _ in range(70):
                    cur = newest_download(download_dir)
                    if cur and (
                        before_name is None
                        or cur.name != before_name
                        or cur.stat().st_mtime > before_m + 0.0001
                    ):
                        got = cur
                        break
                    time.sleep(0.2)

                if not got:
                    row["status"] = "download_timeout"
                    run_log["rows"].append(row)
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    continue

                img_md5 = md5_file(got)
                row["image_md5"] = img_md5
                row["download_name"] = got.name

                if img_md5 in seen_hash:
                    row["status"] = "duplicate_image_hash"
                    run_log["rows"].append(row)
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    continue

                target.write_bytes(got.read_bytes())
                seen_hash.add(img_md5)
                used_scenes.add(scene_id)
                saved += 1
                progressed = True
                row["status"] = "saved"
                row["target"] = str(target)
                run_log["rows"].append(row)
                print(f"OK scene={scene_id:03d} score={score:.3f} file={got.name}")

                try:
                    page.keyboard.press("Escape")
                    time.sleep(0.2)
                except Exception:
                    pass

            page.mouse.wheel(0, 1800)
            time.sleep(0.35)
            if progressed:
                idle_rounds = 0
            else:
                idle_rounds += 1

    log_path = log_dir / f"gemini_feed_walk_run_{int(time.time())}.json"
    log_path.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", saved)
    print("log", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
