#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[3]


def _is_dialogue_like(text: str) -> bool:
    if any(q in text for q in ['"', "'", "“", "”", "‘", "’", "「", "」"]):
        return True
    return bool(re.search(r"(말하|묻|답하|외치|소리치|속삭|중얼|대꾸)", text))


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit clip character alignment against scene script text")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--fail-on-mismatch", action="store_true")
    args = ap.parse_args()

    project_path = ROOT / "work" / args.story_id / "out" / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"project.json not found: {project_path}")

    data = json.loads(project_path.read_text(encoding="utf-8"))
    scenes = [s for s in data.get("scenes", []) if isinstance(s, dict)]
    char_map = {c["id"]: c for c in data.get("characters", []) if isinstance(c, dict) and c.get("id")}
    char_path_to_id: Dict[str, str] = {}

    for cid, cobj in char_map.items():
        if not isinstance(cobj, dict):
            continue
        img = cobj.get("image")
        if isinstance(img, dict):
            p = str(img.get("path") or "").strip()
            cp = str(img.get("cutout_path") or "").strip()
            if p:
                char_path_to_id[str(Path(p).resolve())] = str(cid)
            if cp:
                char_path_to_id[str(Path(cp).resolve())] = str(cid)
        images = cobj.get("images")
        if isinstance(images, dict):
            for _, vmeta in images.items():
                if not isinstance(vmeta, dict):
                    continue
                p2 = str(vmeta.get("path") or "").strip()
                cp2 = str(vmeta.get("cutout_path") or "").strip()
                if p2:
                    char_path_to_id[str(Path(p2).resolve())] = str(cid)
                if cp2:
                    char_path_to_id[str(Path(cp2).resolve())] = str(cid)

    rows: List[Dict[str, Any]] = []
    total = 0
    ok = 0
    warning = 0
    mismatch = 0

    for s in scenes:
        total += 1
        sid = int(s.get("id") or 0)
        text = str(s.get("text") or "")
        scene_char_ids = [str(x) for x in (s.get("characters") or []) if isinstance(x, str)]
        img_meta = s.get("image") if isinstance(s.get("image"), dict) else {}

        mentioned_ids: List[str] = []
        for cid in scene_char_ids:
            cobj = char_map.get(cid)
            if not isinstance(cobj, dict):
                continue
            tokens: List[str] = []
            name = str(cobj.get("name") or "").strip()
            if name:
                tokens.append(name)
            aliases = cobj.get("aliases") if isinstance(cobj.get("aliases"), list) else []
            for a in aliases:
                aa = str(a or "").strip()
                if aa:
                    tokens.append(aa)
            if any(tok in text for tok in tokens):
                mentioned_ids.append(cid)

        displayed_ids: List[str] = []
        ph = (img_meta or {}).get("prompt_history")
        if isinstance(ph, list):
            for ent in reversed(ph):
                if not isinstance(ent, dict):
                    continue
                phase = str(ent.get("phase") or "")
                if phase.startswith("compose_from_refs"):
                    lh = ent.get("layout_hint")
                    if isinstance(lh, dict):
                        scids = lh.get("selected_char_ids")
                        if isinstance(scids, list):
                            displayed_ids = [str(x) for x in scids if str(x)]
                    if not displayed_ids:
                        refs = ent.get("references")
                        if isinstance(refs, list):
                            for rp in refs:
                                rps = str(rp or "").strip()
                                if not rps:
                                    continue
                                rid = char_path_to_id.get(str(Path(rps).resolve()))
                                if rid and rid not in displayed_ids:
                                    displayed_ids.append(rid)
                    if displayed_ids:
                        break
        if not displayed_ids:
            manual_subject = str((img_meta or {}).get("subject_char_id") or "").strip()
            if manual_subject:
                displayed_ids = [manual_subject]

        issues: List[str] = []
        for did in displayed_ids:
            if did not in scene_char_ids:
                issues.append(f"displayed_not_in_scene_characters:{did}")

        if _is_dialogue_like(text) and mentioned_ids and len(displayed_ids) == 1:
            if displayed_ids[0] not in mentioned_ids:
                issues.append(
                    "dialogue_subject_mismatch:"
                    f"displayed={displayed_ids[0]} expected_one_of={','.join(mentioned_ids)}"
                )

        status = "ok"
        if issues:
            status = "mismatch"
            mismatch += 1
        elif not displayed_ids:
            status = "warning"
            warning += 1
            issues.append("no_displayed_character_metadata")
        else:
            ok += 1

        rows.append(
            {
                "scene_id": sid,
                "status": status,
                "scene_characters": scene_char_ids,
                "mentioned_characters": mentioned_ids,
                "displayed_characters": displayed_ids,
                "issues": issues,
            }
        )

    out = {
        "summary": {"total": total, "ok": ok, "warning": warning, "mismatch": mismatch},
        "items": rows,
    }
    out_path = ROOT / "work" / args.story_id / "out" / "clip_character_audit.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"saved: {out_path}")
    print(json.dumps(out["summary"], ensure_ascii=False))
    if mismatch > 0 and args.fail_on_mismatch:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
