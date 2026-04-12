#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[3]


def _load_project(story_id: str) -> Dict[str, Any]:
    path = ROOT / "work" / story_id / "out" / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"missing project.json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _token_in_text(token: str, text: str) -> bool:
    token = str(token or "").strip()
    if not token:
        return False
    if re.fullmatch(r"[A-Za-z0-9 _\-']+", token):
        if re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE):
            return True
        compact_token = re.sub(r"[\s_\-']", "", token).lower()
        compact_text = re.sub(r"[\s_\-']", "", text).lower()
        return bool(compact_token and compact_token in compact_text)
    return token in text


def _character_tokens(char_obj: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    name = str(char_obj.get("name") or "").strip()
    if name:
        out.append(name)
    aliases = char_obj.get("aliases")
    if isinstance(aliases, list):
        for a in aliases:
            aa = str(a or "").strip()
            if aa:
                out.append(aa)
    return out


def _mentions_for_text(
    text: str, scene_char_ids: List[str], char_map: Dict[str, Dict[str, Any]]
) -> Set[str]:
    mentioned: Set[str] = set()
    for cid in scene_char_ids:
        cobj = char_map.get(cid)
        if not isinstance(cobj, dict):
            continue
        for tok in _character_tokens(cobj):
            if _token_in_text(tok, text):
                mentioned.add(cid)
                break
    return mentioned


def _mentions_for_prompt(prompt: str, char_map: Dict[str, Dict[str, Any]]) -> Set[str]:
    mentioned: Set[str] = set()
    for cid, cobj in char_map.items():
        if not isinstance(cobj, dict):
            continue
        for tok in _character_tokens(cobj):
            if _token_in_text(tok, prompt):
                mentioned.add(cid)
                break
    return mentioned


def _audit_scene(scene: Dict[str, Any], char_map: Dict[str, Dict[str, Any]]) -> Tuple[str, List[str], Dict[str, Any]]:
    sid = int(scene.get("id", 0) or 0)
    text = str(scene.get("text") or "")
    prompt = str(scene.get("llm_clip_prompt") or "")
    scene_char_ids = [str(x) for x in (scene.get("characters") or []) if isinstance(x, str)]

    text_mentions = _mentions_for_text(text, scene_char_ids, char_map)
    prompt_mentions = _mentions_for_prompt(prompt, char_map)

    issues: List[str] = []

    out_of_scene = sorted([cid for cid in prompt_mentions if cid not in scene_char_ids])
    if out_of_scene:
        issues.append("prompt_mentions_character_outside_scene")

    if text_mentions and prompt_mentions and text_mentions.isdisjoint(prompt_mentions):
        issues.append("text_prompt_explicit_name_mismatch")

    status = "ok"
    if issues:
        status = "candidate"

    detail = {
        "scene_id": sid,
        "status": status,
        "scene_characters": scene_char_ids,
        "text_mentions": sorted(text_mentions),
        "prompt_mentions": sorted(prompt_mentions),
        "issues": issues,
    }
    return status, issues, detail


def _save_markdown(path: Path, story_id: str, summary: Dict[str, int], items: List[Dict[str, Any]]) -> None:
    lines: List[str] = []
    lines.append(f"# script-vs-prompt role audit ({story_id})")
    lines.append("")
    lines.append(f"- total_scenes: {summary['total_scenes']}")
    lines.append(f"- ok: {summary['ok']}")
    lines.append(f"- candidates: {summary['candidates']}")
    lines.append("")
    if summary["candidates"] == 0:
        lines.append("No candidate mismatches found.")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    for it in items:
        if it.get("status") != "candidate":
            continue
        lines.append(f"## scene {it['scene_id']}")
        issues = ", ".join(it.get("issues") or [])
        lines.append(f"- issues: {issues}")
        lines.append(f"- scene_characters: {', '.join(it.get('scene_characters') or []) or '-'}")
        lines.append(f"- text_mentions: {', '.join(it.get('text_mentions') or []) or '-'}")
        lines.append(f"- prompt_mentions: {', '.join(it.get('prompt_mentions') or []) or '-'}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit role consistency between script text and clip prompt mentions")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--fail-on-candidate", action="store_true")
    args = ap.parse_args()

    project = _load_project(args.story_id)
    scenes = [s for s in (project.get("scenes") or []) if isinstance(s, dict)]
    char_map: Dict[str, Dict[str, Any]] = {
        str(c.get("id")): c
        for c in (project.get("characters") or [])
        if isinstance(c, dict) and str(c.get("id") or "").strip()
    }

    items: List[Dict[str, Any]] = []
    candidates = 0
    ok = 0
    for scene in scenes:
        status, _, detail = _audit_scene(scene, char_map)
        items.append(detail)
        if status == "candidate":
            candidates += 1
        else:
            ok += 1

    out_dir = ROOT / "work" / args.story_id / "out"
    out_json = out_dir / "script_prompt_role_audit.json"
    out_md = out_dir / "script_prompt_role_audit.md"
    summary = {"total_scenes": len(scenes), "ok": ok, "candidates": candidates}
    out = {"story_id": args.story_id, "summary": summary, "items": items}
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _save_markdown(out_md, args.story_id, summary, items)

    print(json.dumps({"ok": candidates == 0, "summary": summary, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False))
    if candidates > 0 and args.fail_on_candidate:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
