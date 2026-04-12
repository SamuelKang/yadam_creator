#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <story-id> [--apply]" >&2
  exit 2
fi

story_id="$1"
mode="${2:-}"

if [[ ! -f "stories/${story_id}.txt" ]]; then
  echo "missing story file: stories/${story_id}.txt" >&2
  exit 1
fi

if [[ ! -f "work/${story_id}/out/project.json" ]]; then
  echo "missing project file: work/${story_id}/out/project.json" >&2
  exit 1
fi

echo "[1/8] style lock check"
python skills/prompt_qc_flow/scripts/enforce_flow_style_lock.py --story-id "${story_id}"

echo "[2/8] post-step8 prompt gate"
python skills/prompt_qc_flow/scripts/check_post_step8_prompt_gate.py --story-id "${story_id}"

echo "[3/8] review clip prompts"
python skills/prompt_qc_flow/scripts/review_clip_prompts.py --story-id "${story_id}"

echo "[4/8] role/place/wardrobe-prop drift scan"
python skills/prompt_qc_flow/scripts/scan_role_place_prop_drift.py --story-id "${story_id}"

echo "[5/8] script-vs-prompt role audit"
python skills/prompt_qc_flow/scripts/audit_script_prompt_roles.py --story-id "${story_id}"

echo "[6/8] semantic risk audit"
python skills/prompt_qc_flow/scripts/audit_prompt_semantic_risks.py --story-id "${story_id}"

if [[ "${mode}" == "--apply" ]]; then
  echo "[7/8] apply continuity + style + drift locks"
  python skills/prompt_qc_flow/scripts/repair_clip_context_continuity.py --story-id "${story_id}" --apply
  python skills/prompt_qc_flow/scripts/enforce_flow_style_lock.py --story-id "${story_id}" --apply
  python skills/prompt_qc_flow/scripts/scan_role_place_prop_drift.py --story-id "${story_id}" --apply
  python skills/prompt_qc_flow/scripts/audit_prompt_semantic_risks.py --story-id "${story_id}" --apply

  echo "[8/8] re-check after repair"
  python skills/prompt_qc_flow/scripts/enforce_flow_style_lock.py --story-id "${story_id}"
  python skills/prompt_qc_flow/scripts/check_post_step8_prompt_gate.py --story-id "${story_id}"
  python skills/prompt_qc_flow/scripts/review_clip_prompts.py --story-id "${story_id}"
  python skills/prompt_qc_flow/scripts/scan_role_place_prop_drift.py --story-id "${story_id}"
  python skills/prompt_qc_flow/scripts/audit_script_prompt_roles.py --story-id "${story_id}"
  python skills/prompt_qc_flow/scripts/audit_prompt_semantic_risks.py --story-id "${story_id}"
else
  if [[ -n "${mode}" ]]; then
    echo "unknown option: ${mode}" >&2
    exit 2
  fi
  echo "[7/8] skip apply (check-only mode)"
  echo "[8/8] done"
fi
