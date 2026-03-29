from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, List

from yadam.gen.comfy_client import ComfyUIImageClient
from yadam.gen.image_client import ImageGenRequest


def _load_project(project_path: Path) -> dict:
    return json.loads(project_path.read_text(encoding="utf-8"))


def _find_char(project: dict, char_id: str) -> dict:
    for c in project.get("characters", []):
        if isinstance(c, dict) and str(c.get("id", "")).strip() == char_id:
            return c
    raise ValueError(f"character not found: {char_id}")


def _build_prompt(name: str) -> str:
    return (
        f"single Korean Joseon character sheet of {name}, one human male, full body, centered, standing pose, "
        "young adult male (late teens to early 20s), realistic adult body proportions, not child, not chibi, "
        "fully clothed in traditional Joseon hanbok (jeogori and durumagi over baji), modest historical outfit, "
        "no exposed chest, no exposed torso, no nudity, "
        "traditional Joseon male hairstyle: neat sangtu(topknot) with smooth tied hairline, clean forehead, "
        "no loose strands, no modern hairstyle, no fringe bangs, no undercut, no dyed hair, "
        "detailed Korean face with visible eyes, nose, mouth, eyebrows, natural expression, "
        "head-to-toe composition, entire body in frame, feet fully visible, full legs and shoes visible, "
        "traditional Joseon footwear only: plain white beoseon socks, simple Joseon shoes, no modern sneakers, "
        "clean line art, flat cel shading, white seamless studio background, isolated subject, "
        "no props, no architecture, no scenery, no extra person, no animal, no text, no letters, no calligraphy."
    )


def _negative_prompt() -> str:
    return (
        "text, letters, words, calligraphy, hanja, hangul, watermark, logo, stamp, seal, signature, subtitle, signboard, "
        "background scenery, architecture, hanok, street, courtyard, people, crowd, extra person, extra animal, "
        "faceless, blank face, missing eyes, missing nose, missing mouth, "
        "modern haircut, short fade haircut, undercut, perm, dyed hair, bangs over forehead, "
        "child, kid, toddler, chibi, baby face, oversized head, modern sneakers, running shoes, lace-up shoes, "
        "nude, nudity, naked, bare chest, exposed torso, exposed genitals"
    )


def _make_client(workflow_path: Path, model_name: str) -> ComfyUIImageClient:
    return ComfyUIImageClient(
        base_url=os.getenv("COMFYUI_URL", "https://cloud.comfy.org/api").strip().strip("'\""),
        workflow_path=str(workflow_path),
        model=model_name,
        timeout_sec=900,
        negative_prompt=_negative_prompt(),
        api_key=os.getenv("COMFYUI_API_KEY", "").strip(),
        api_key_header=os.getenv("COMFYUI_API_KEY_HEADER", "X-API-Key").strip(),
    )


def _iter_seeds(seed_csv: str) -> Iterable[int]:
    for s in seed_csv.split(","):
        t = s.strip()
        if not t:
            continue
        yield int(t)


def run_base(
    root: Path,
    story_id: str,
    char_id: str,
    model_name: str,
    seeds: List[int],
    workflow_path: str = "",
) -> Path:
    if workflow_path.strip():
        workflow = Path(workflow_path).expanduser().resolve()
    else:
        workflow = root / "yadam" / "config" / "comfy_workflows" / "yadam_api_flux_schnell_dualclip4_placeholders.json"
    project_path = root / "work" / story_id / "out" / "project.json"
    out_dir = root / "work" / story_id / "characters" / f"candidates_{char_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    project = _load_project(project_path)
    c = _find_char(project, char_id)
    name = str(c.get("name") or char_id)
    prompt = _build_prompt(name)

    client = _make_client(workflow, model_name)
    print(f"[base] workflow={workflow.name} model={model_name} char={char_id} seeds={len(seeds)}")
    for i, seed in enumerate(seeds, start=1):
        out = out_dir / f"{char_id}_seed{seed}.jpg"
        req = ImageGenRequest(prompt=prompt, aspect_ratio="3:4", seed=seed)
        resp = client.generate(req)
        out.write_bytes(resp.image_bytes)
        print(f"[{i}/{len(seeds)}] ok seed={seed} -> {out.name}")
    return out_dir


def run_refine(
    root: Path,
    story_id: str,
    char_id: str,
    model_name: str,
    reference_image: Path,
    seed: int,
    workflow_path: str = "",
) -> Path:
    if workflow_path.strip():
        workflow = Path(workflow_path).expanduser().resolve()
    else:
        workflow = root / "yadam" / "config" / "comfy_workflows" / "yadam_api_flux_schnell_refine_img2img_placeholders.json"
    project_path = root / "work" / story_id / "out" / "project.json"
    out_path = root / "work" / story_id / "characters" / f"{char_id}_refined.jpg"
    if not reference_image.exists():
        raise FileNotFoundError(f"missing reference image: {reference_image}")

    project = _load_project(project_path)
    c = _find_char(project, char_id)
    name = str(c.get("name") or char_id)

    prompt = (
        f"Korean Joseon male {name} character sheet, single subject, full body, centered, plain white background. "
        "Keep same identity, same face, same hairstyle and same outfit silhouette as reference image. "
        "Refine footwear to traditional Joseon style, remove modern sneaker details, keep beoseon socks, no text."
    )

    client = _make_client(workflow, model_name)
    req = ImageGenRequest(
        prompt=prompt,
        aspect_ratio="3:4",
        seed=seed,
        reference_image_paths=(str(reference_image),),
    )
    resp = client.generate(req)
    out_path.write_bytes(resp.image_bytes)
    print(f"[refine] ok -> {out_path}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Comfy Cloud charsheet workflow runner")
    ap.add_argument("--story-id", required=True)
    ap.add_argument("--char-id", required=True)
    ap.add_argument("--mode", choices=["base", "refine"], required=True)
    ap.add_argument("--model", default="flux1-schnell.safetensors")
    ap.add_argument("--seeds", default="10121,20231,30341,40451,50561,60671,70781,80891")
    ap.add_argument("--seed", type=int, default=917071)
    ap.add_argument("--reference-image", default="")
    ap.add_argument("--workflow-path", default="")
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    if args.mode == "base":
        seeds = list(_iter_seeds(args.seeds))
        if not seeds:
            raise ValueError("no seeds provided")
        run_base(root, args.story_id, args.char_id, args.model, seeds, args.workflow_path)
    else:
        ref = Path(args.reference_image).expanduser().resolve()
        run_refine(root, args.story_id, args.char_id, args.model, ref, int(args.seed), args.workflow_path)


if __name__ == "__main__":
    main()
