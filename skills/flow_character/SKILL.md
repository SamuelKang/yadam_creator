---
name: flow_character
description: Use this skill to create project-level Flow character reference seed images first, then save reusable reference points to `flow_seed_refs.json`.
---

# flow_character

Use this skill when you want to:

1. generate character reference seed cards in the current/new Flow project
2. save their reference points (`src + prompt + role`) for later scene generation

## Scope

- Input:
  - `work/<story-id>/out/project.json` (`characters` metadata)
- Output:
  - `work/<story-id>/out/flow_seed_refs.json`

## Scripts

- Seed generator:
  - `skills/flow_character/scripts/init_flow_character_seeds.py`
- Reference-point collector:
  - `skills/flow_character/scripts/collect_flow_seed_refs.py`
- One-shot setup (seed + collect):
  - `skills/flow_character/scripts/run_flow_character_ref_setup.sh`

## Recommended One-shot

```bash
STORY_ID=story17 \
FLOW_SEED_CHAR_IDS=char_001,char_002,char_003,char_004,char_005 \
FLOW_IGNORE_LOCAL_FILES=1 \
FLOW_REUSE_CURRENT_PROJECT=0 \
skills/flow_character/scripts/run_flow_character_ref_setup.sh
```

## Runtime knobs

- `STORY_ID`: story id
- `FLOW_SEED_CHAR_IDS`: comma-separated char ids
- `FLOW_IGNORE_LOCAL_FILES`:
  - `1`: do not upload local files, prompt-only seed generation
  - `0`: use local files when available
- `FLOW_REUSE_CURRENT_PROJECT`:
  - `1`: append in current Flow project
  - `0`: create/select a new project first

