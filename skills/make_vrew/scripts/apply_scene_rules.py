from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yadam.gen.image_client import ImageClient, ImageGenRequest, ImageGenResponse
from yadam.pipeline.orchestrator import Orchestrator, PipelineConfig


class _NoopImageClient(ImageClient):
    def generate(self, req: ImageGenRequest) -> ImageGenResponse:
        raise RuntimeError("image generation is not available in apply_scene_rules.py")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Apply auto scene rules from project.json and manual story rule YAMLs to project.json."
    )
    ap.add_argument("--story-id", required=True, help="예: story14")
    ap.add_argument("--project-root", default=".", help="프로젝트 루트(기본: 현재 폴더)")
    ap.add_argument("--profiles", default="yadam/config/default_profiles.yaml")
    ap.add_argument("--era", default="joseon_yadam")
    ap.add_argument("--style", default="k_webtoon")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    script_path = root / "stories" / f"{args.story_id}.txt"
    if not script_path.exists():
        raise FileNotFoundError(f"story 파일이 없습니다: {script_path}")

    cfg = PipelineConfig(
        base_dir=str(root / "work" / args.story_id),
        profiles_yaml=str(root / args.profiles),
        era_profile=args.era,
        style_profile=args.style,
        input_script_path=str(script_path),
        interactive=False,
    )
    orch = Orchestrator(cfg, img_client=_NoopImageClient(), exporter=None)
    project = orch.db.load()
    if not project:
        raise FileNotFoundError(f"project.json 이 없습니다: {orch.db.path}")

    scenes = [s for s in project.get("scenes", []) if isinstance(s, dict)]
    chars = [c for c in project.get("characters", []) if isinstance(c, dict)]
    places = [p for p in project.get("places", []) if isinstance(p, dict)]
    if not scenes:
        raise RuntimeError("project.json 에 scenes 가 없습니다.")

    auto_rules = ((project.get("project") or {}).get("auto_scene_rules") or {})
    orch._apply_variant_overrides(
        scenes,
        chars,
        overrides=list(auto_rules.get("variant_overrides") or []),
    )
    orch._apply_scene_bindings(
        scenes,
        chars,
        places,
        bindings=list(auto_rules.get("scene_bindings") or []),
    )
    orch._apply_variant_overrides(scenes, chars)
    orch._apply_scene_bindings(scenes, chars, places)
    orch._update_used_by_scenes(scenes, chars, places)

    project.setdefault("project", {})
    project["project"]["phase"] = "structure_fixed"
    project["project"]["phase_detail"] = "codex_rules_applied"
    orch.db.save(project)
    print(f"[INFO] applied scene rules: {orch.db.path}")


if __name__ == "__main__":
    main()
