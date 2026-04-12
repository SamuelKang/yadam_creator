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
    rows: list[dict[str, Any]] = []
    for i, s in enumerate(scenes, start=1):
        if max_scene and i > max_scene:
            break
        prompt = (
            s.get("image", {}).get("prompt_used")
            or s.get("llm_clip_prompt")
            or ""
        ).strip()
        if not prompt:
            continue
        rows.append(
            {
                "scene": i,
                "prompt": prompt,
                "prompt_hash": hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10],
            }
        )
    return rows


def newest_download(download_dir: Path) -> Path | None:
    files = sorted(download_dir.glob(DOWNLOAD_GLOB), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def image_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def pick_best_page(browser) -> Any | None:
    best = None
    best_score = -1
    for ctx in browser.contexts:
        for pg in ctx.pages:
            url = pg.url or ""
            if "gemini.google.com" not in url:
                continue
            try:
                score = pg.get_by_role("button", name="원본 크기 이미지 다운로드").count()
            except Exception:
                score = 0
            if score > best_score:
                best_score = score
                best = pg
    return best


def collect_cards(page) -> list[dict[str, Any]]:
    js = r'''() => {
      const btnSel = 'button[aria-label="원본 크기 이미지 다운로드"]';
      const btns = [...document.querySelectorAll(btnSel)];
      const out = [];

      function cleanText(t) {
        return (t || '').replace(/\s+/g, ' ').trim();
      }

      for (let i = 0; i < btns.length; i++) {
        const b = btns[i];
        let node = b;
        let found = null;

        for (let up = 0; up < 14 && node; up++) {
          node = node.parentElement;
          if (!node) break;
          const t = cleanText(node.innerText || '');
          if (!t) continue;
          if (t.includes('Primary subjects:') || t.includes('Visible action:') || t.includes('Ghibli-inspired')) {
            found = t;
            break;
          }
        }

        const rect = b.getBoundingClientRect();
        out.push({
          btn_index: i,
          y: rect ? rect.y : 0,
          text: found || ''
        });
      }

      return out;
    }'''
    rows = page.evaluate(js) or []
    rows.sort(key=lambda r: r.get("y", 0))
    return rows


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
        scene_id = int(s["scene"])
        prompt = str(s["prompt"])
        needle = prompt[:120]
        if not needle:
            continue
        idx = body_text.find(needle)
        if idx >= 0:
            hits.append((idx, scene_id))

    hits.sort(key=lambda x: x[0])
    ordered = [scene_id for _, scene_id in hits]
    # keep order, remove duplicates
    out: list[int] = []
    seen: set[int] = set()
    for sid in ordered:
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
        if len(out) >= max_count:
            break
    return out


def best_scene_match(card_text: str, scenes: list[dict[str, Any]], used: set[int]) -> tuple[int | None, float]:
    if not card_text:
        return None, 0.0

    best_scene = None
    best_score = 0.0
    card_norm = " ".join(card_text.split())

    for s in scenes:
        scene_id = int(s["scene"])
        if scene_id in used:
            continue
        prompt = s["prompt"]
        prompt_norm = " ".join(prompt.split())

        # weighted matching: exact substring bonus + sequence ratio
        ratio = difflib.SequenceMatcher(None, card_norm[:800], prompt_norm[:800]).ratio()
        bonus = 0.0
        if card_norm[:120] and card_norm[:120] in prompt_norm:
            bonus += 0.2
        if "Primary subjects:" in card_norm and "Primary subjects:" in prompt_norm:
            bonus += 0.05
        if "Visible action:" in card_norm and "Visible action:" in prompt_norm:
            bonus += 0.05

        score = min(1.0, ratio + bonus)
        if score > best_score:
            best_score = score
            best_scene = scene_id

    return best_scene, best_score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--max-scene", type=int, default=40)
    ap.add_argument("--min-score", type=float, default=0.55)
    args = ap.parse_args()

    base = Path("work") / args.story_id
    project_json = base / "out" / "project.json"
    out_dir = base / "clips_original"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = base / "out"
    log_dir.mkdir(parents=True, exist_ok=True)

    download_dir = Path.home() / "Downloads"
    scenes = load_scene_prompts(project_json, args.max_scene)
    if not scenes:
        print("FAIL:no_scenes")
        return 1

    used_scenes = {int(p.stem) for p in out_dir.glob("*.png") if p.stem.isdigit()}
    seen_md5 = {image_md5(p) for p in out_dir.glob("*.png")}

    run_log: dict[str, Any] = {
        "ts": int(time.time()),
        "story_id": args.story_id,
        "max_scene": args.max_scene,
        "min_score": args.min_score,
        "rows": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = pick_best_page(browser)
        if not page:
            print("FAIL:no_gemini_page")
            return 2

        page.bring_to_front()
        time.sleep(0.4)

        cards = collect_cards(page)
        print("cards", len(cards))
        # fallback: when card text is not readable (e.g. enlarged viewer / virtualized DOM),
        # infer scene order from body text and button order.
        fallback_order = extract_scene_order_from_body(page, scenes, len(cards))

        for i, card in enumerate(cards):
            idx = int(card["btn_index"])
            text = card.get("text", "")
            scene_id, score = best_scene_match(text, scenes, used_scenes)
            if (
                (not text or score < args.min_score)
                and i < len(fallback_order)
                and fallback_order[i] not in used_scenes
            ):
                scene_id = fallback_order[i]
                score = max(score, 0.62)

            row: dict[str, Any] = {
                "btn_index": idx,
                "scene": scene_id,
                "score": round(score, 4),
                "text_preview": (text[:180] if text else ""),
                "status": "",
            }

            if not scene_id or score < args.min_score:
                row["status"] = "unmatched"
                run_log["rows"].append(row)
                continue

            target = out_dir / f"{scene_id:03d}.png"
            if target.exists():
                row["status"] = "already_exists"
                run_log["rows"].append(row)
                used_scenes.add(scene_id)
                continue

            before = newest_download(download_dir)
            before_name = before.name if before else None
            before_m = before.stat().st_mtime if before else 0.0

            click_state = page.evaluate(
                '''(i) => {
                  const btns=[...document.querySelectorAll('button[aria-label="원본 크기 이미지 다운로드"]')];
                  if (i < 0 || i >= btns.length) return 'NO_BTN';
                  const b = btns[i];
                  b.scrollIntoView({block:'center'});
                  b.click();
                  return 'CLICKED';
                }''',
                idx,
            )
            if click_state != "CLICKED":
                row["status"] = f"click_fail:{click_state}"
                run_log["rows"].append(row)
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
                continue

            md5 = image_md5(got)
            row["image_md5"] = md5
            row["download_name"] = got.name

            if md5 in seen_md5:
                row["status"] = "duplicate_image_hash"
                run_log["rows"].append(row)
                continue

            target.write_bytes(got.read_bytes())
            seen_md5.add(md5)
            used_scenes.add(scene_id)

            row["status"] = "saved"
            row["target"] = str(target)
            run_log["rows"].append(row)
            print(f"OK scene={scene_id:03d} btn={idx} score={score:.3f} file={got.name}")

    out_log = log_dir / f"gemini_card_pair_run_{int(time.time())}.json"
    out_log.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")

    saved = sum(1 for r in run_log["rows"] if r.get("status") == "saved")
    print("saved", saved)
    print("log", out_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
