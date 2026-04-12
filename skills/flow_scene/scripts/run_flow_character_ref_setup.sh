#!/usr/bin/env bash
set -euo pipefail

STORY_ID=${STORY_ID:-story16}
FLOW_SEED_CHAR_IDS=${FLOW_SEED_CHAR_IDS:-char_001,char_002}
FLOW_IGNORE_LOCAL_FILES=${FLOW_IGNORE_LOCAL_FILES:-1}
FLOW_REUSE_CURRENT_PROJECT=${FLOW_REUSE_CURRENT_PROJECT:-0}

SEED_ARGS=()
if [[ "$FLOW_IGNORE_LOCAL_FILES" == "1" ]]; then
  SEED_ARGS+=(--ignore-local-files)
fi
if [[ "$FLOW_REUSE_CURRENT_PROJECT" == "1" ]]; then
  SEED_ARGS+=(--reuse-current-project)
fi

echo "[FLOW] character ref seed generation story=${STORY_ID} chars=${FLOW_SEED_CHAR_IDS}"
.venv/bin/python skills/flow_scene/scripts/init_flow_new_project_with_char_seeds.py \
  --story-id "${STORY_ID}" \
  --char-ids "${FLOW_SEED_CHAR_IDS}" \
  "${SEED_ARGS[@]}"

echo "[FLOW] collect seed reference points"
.venv/bin/python skills/flow_scene/scripts/collect_flow_seed_refs.py \
  --story-id "${STORY_ID}"

echo "[FLOW] done: work/${STORY_ID}/out/flow_seed_refs.json"
