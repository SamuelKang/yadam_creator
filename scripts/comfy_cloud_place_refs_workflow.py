from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable

from yadam.gen.comfy_client import ComfyUIImageClient
from yadam.gen.image_client import ImageGenRequest


def _load_project(project_path: Path) -> Dict[str, object]:
    return json.loads(project_path.read_text(encoding="utf-8"))


def _safe_name(text: str) -> str:
    s = re.sub(r"\s+", "_", str(text or "").strip())
    s = re.sub(r"[^0-9A-Za-z가-힣_]+", "", s)
    return s or "place"


def _iter_place_ids(csv_text: str) -> Iterable[str]:
    for raw in (csv_text or "").split(","):
        pid = raw.strip()
        if pid:
            yield pid


def _seed_for_place(place_id: str) -> int:
    # Deterministic seed from place id; stable across sessions.
    value = 0
    for i, ch in enumerate(place_id.encode("utf-8"), start=1):
        value += i * ch
    return 10000 + (value % 900000)


def _style_prefix() -> str:
    return (
        "Korean historical illustration style, semi-realistic cinematic matte painting, "
        "painterly brush texture, detailed environment concept art, period-accurate Joseon architecture, "
        "not a photo, no characters"
    )


def _negative_prompt() -> str:
    return (
        "photorealistic photo, camera lens realism, text, letters, words, typography, title, caption, subtitle, "
        "watermark, logo, signboard, calligraphy, hangul, hanja, people, person, crowd, animal, portrait, close-up face, "
        "modern objects, electric wires, power line, cable, telephone pole, utility pole, street lamp, traffic sign, car, asphalt road"
    )


def _build_prompt(place: Dict[str, object]) -> str:
    image = place.get("image") if isinstance(place.get("image"), dict) else {}
    prompt_used = str((image or {}).get("prompt_used") or "").strip()
    if prompt_used:
        return f"{_style_prefix()}. {prompt_used}"

    name = str(place.get("name") or place.get("id") or "place")
    anchors = [
        str(x).strip()
        for x in (place.get("visual_anchors") or [])
        if isinstance(x, str) and str(x).strip()
    ]
    anchor_line = ", ".join(anchors[:8]) if anchors else "Joseon environment, no modern infrastructure"
    return (
        f"{_style_prefix()}. "
        f"Joseon place reference environment shot of {name}. "
        f"Visual anchors: {anchor_line}. "
        "16:9 full-frame background, no people, no text."
    )


def _make_client(root: Path, workflow_path: str, model_name: str, timeout_sec: int) -> ComfyUIImageClient:
    workflow = (
        Path(workflow_path).expanduser().resolve()
        if workflow_path.strip()
        else root / "yadam" / "config" / "comfy_workflows" / "yadam_api_z_image_turbo_placeholders.json"
    )
    return ComfyUIImageClient(
        base_url=os.getenv("COMFYUI_URL", "https://cloud.comfy.org/api").strip().strip("'\""),
        workflow_path=str(workflow),
        model=model_name,
        timeout_sec=timeout_sec,
        negative_prompt=_negative_prompt(),
        api_key=os.getenv("COMFYUI_API_KEY", "").strip(),
        api_key_header=os.getenv("COMFYUI_API_KEY_HEADER", "X-API-Key").strip() or "X-API-Key",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate place references via Comfy Cloud + Z-Image Turbo")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--place-ids", default="", help="Comma-separated place ids (default: all places)")
    ap.add_argument("--model", default="z_image_turbo_bf16.safetensors")
    ap.add_argument("--workflow-path", default="")
    ap.add_argument("--aspect-ratio", default="16:9")
    ap.add_argument("--timeout-sec", type=int, default=900)
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    project_path = root / "work" / args.story_id / "out" / "project.json"
    places_dir = root / "work" / args.story_id / "places"
    places_dir.mkdir(parents=True, exist_ok=True)

    if not project_path.exists():
        raise FileNotFoundError(f"missing project.json: {project_path}")

    project = _load_project(project_path)
    places = [p for p in (project.get("places") or []) if isinstance(p, dict)]
    if not places:
        raise ValueError(f"no places found in {project_path}")

    selected_ids = set(_iter_place_ids(args.place_ids))
    if selected_ids:
        places = [p for p in places if str(p.get("id") or "") in selected_ids]
        if not places:
            raise ValueError(f"no matching place ids: {sorted(selected_ids)}")

    client = _make_client(root, args.workflow_path, args.model, max(10, int(args.timeout_sec)))

    for i, place in enumerate(places, start=1):
        pid = str(place.get("id") or f"place_{i:03d}")
        name = str(place.get("name") or pid)
        safe = _safe_name(name)
        out = places_dir / f"{pid}_{safe}.jpg"

        seed = _seed_for_place(pid)
        image = place.get("image") if isinstance(place.get("image"), dict) else {}
        if isinstance(image, dict) and image.get("seed") is not None:
            try:
                seed = int(image.get("seed"))
            except Exception:
                pass

        prompt = _build_prompt(place)
        req = ImageGenRequest(prompt=prompt, aspect_ratio=args.aspect_ratio, seed=seed)
        resp = client.generate(req)
        out.write_bytes(resp.image_bytes)
        print(f"[{i}/{len(places)}] ok {pid} -> {out}")


if __name__ == "__main__":
    main()
