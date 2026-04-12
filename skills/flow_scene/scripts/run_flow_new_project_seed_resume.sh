#!/usr/bin/env bash
set -euo pipefail

STORY_ID=${STORY_ID:-story16}
START=${START:-1}
END=${END:-$(jq '.scenes|length' work/${STORY_ID}/out/project.json)}
FLOW_SEED_CHAR_IDS=${FLOW_SEED_CHAR_IDS:-char_001,char_002}
FLOW_SKIP_CHARACTER_PRECHECK=${FLOW_SKIP_CHARACTER_PRECHECK:-1}

echo "[FLOW] new project + character seed start story=${STORY_ID} chars=${FLOW_SEED_CHAR_IDS}"
.venv/bin/python skills/flow_scene/scripts/init_flow_new_project_with_char_seeds.py \
  --story-id "${STORY_ID}" \
  --char-ids "${FLOW_SEED_CHAR_IDS}"

echo "[FLOW] scene resume start story=${STORY_ID} start=${START} end=${END}"
FLOW_SKIP_CHARACTER_PRECHECK=${FLOW_SKIP_CHARACTER_PRECHECK} \
STORY_ID=${STORY_ID} START=${START} END=${END} \
  skills/flow_scene/scripts/run_flow_resume_loop.sh
