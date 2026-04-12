---
name: flow_scene
description: Use this skill for Google Flow image generation with strict prompt verification. It runs scene-by-scene generation, then validates via card menu `프롬프트 재사용` exact-match before saving clips.
---

# flow_scene

Use this skill when the user asks to run/continue `브라우저-flow` image output for a `story-id` and wants reliable save gating.

## Core Policy

- Generate one scene at a time (`start_scene == end_scene`)
- On first entry, start from a new Flow project
- Generate character seed images first so they appear at the top of the project image list
- After generation, do not trust `error_prompt_required` alone
- Validate using card menu path:
  1. top-left latest card
  2. third icon (`...`)
  3. `프롬프트 재사용`
  4. exact match with scene prompt
- Save only when exact match succeeds

## Scripts

- Verifier:
  - `skills/flow_scene/scripts/verify_scene_reuse_exact.py`
- Resume loop:
  - `skills/flow_scene/scripts/run_flow_resume_loop.sh`
- New-project character seeding:
  - `skills/flow_scene/scripts/init_flow_new_project_with_char_seeds.py`
- Seed reference-point collector:
  - `skills/flow_scene/scripts/collect_flow_seed_refs.py`
- New-project seed + resume:
  - `skills/flow_scene/scripts/run_flow_new_project_seed_resume.sh`
- Character-ref setup (seed + collect):
  - `skills/flow_scene/scripts/run_flow_character_ref_setup.sh`

## Single Scene (recommended when unstable)

```bash
sid=30
.venv/bin/python scripts/playwright_gemini_cdp_batch.py \
  --story-id story16 \
  --url https://labs.google/fx/tools/flow \
  --start-scene $sid \
  --end-scene $sid \
  --overwrite \
  --gen-poll-sec 1.0 \
  --start-fallback-sec 15 \
  --min-post-submit-sec 25 \
  --timeout-sec 240 \
  --cooldown-sec 2 \
  --idle-timeout-sec 90 \
  --idle-stable-sec 2.0 \
  --idle-poll-sec 0.5

.venv/bin/python skills/flow_scene/scripts/verify_scene_reuse_exact.py \
  --story-id story16 \
  --scene-id $sid \
  --top-n 1 \
  --wait-sec 60 \
  --poll-sec 10
```

If top-1 verification fails, regenerate once and retry with `--top-n 3`.

## New Project + Character Seeds + Resume

```bash
STORY_ID=story17 \
FLOW_SEED_CHAR_IDS=char_001,char_002 \
START=1 \
skills/flow_scene/scripts/run_flow_new_project_seed_resume.sh
```

Behavior:

- create/select a new Flow project first
- attach character reference images from `work/<story-id>/characters`
- generate seed cards for selected character ids first
- then continue normal scene generation+verify loop

## Character Ref Setup (seed + reference point save)

Create project-level character reference cards first, then save their reusable
reference points to `work/<story-id>/out/flow_seed_refs.json`.

```bash
STORY_ID=story17 \
FLOW_SEED_CHAR_IDS=char_001,char_002,char_003,char_004,char_005 \
FLOW_IGNORE_LOCAL_FILES=1 \
FLOW_REUSE_CURRENT_PROJECT=0 \
skills/flow_scene/scripts/run_flow_character_ref_setup.sh
```

Notes:

- `FLOW_IGNORE_LOCAL_FILES=1`: generate seed refs from character prompt only (no local image upload).
- `FLOW_REUSE_CURRENT_PROJECT=1`: keep current project and append new seed cards.
- collector stores card `src + prompt + role` in `flow_seed_refs.json`.

## Resume From Scene

```bash
STORY_ID=story16 START=30 skills/flow_scene/scripts/run_flow_resume_loop.sh
```

Behavior:

- Skip already existing `clips/NNN.png|jpg`
- Send `Esc` first, then refresh `/tools/flow` tab once before scene loop starts
- For each scene:
  - generate once
  - verify top-1 with polling
  - if failed: regenerate once + verify top-3
  - if still failed: stop immediately

## Runtime Knobs

Environment variables for `run_flow_resume_loop.sh`:

- `STORY_ID` (default: `story16`)
- `START` (default: `20`)
- `END` (default: last scene in `project.json`)
- `FLOW_USE_PROJECT_REFS`
  - `1`: for each scene, use `scene.characters` to select matching reference points from `flow_seed_refs.json`, drag them as 소재 into prompt box, then generate
  - `0`: legacy generate path
- `FLOW_SKIP_CHARACTER_PRECHECK`
  - `1`: skip precheck gate in legacy path

## Expected Outputs

- Clip files: `work/<story-id>/clips/NNN.png`
- Loop log: `work/<story-id>/logs/flow_resume_loop_<ts>.log`
