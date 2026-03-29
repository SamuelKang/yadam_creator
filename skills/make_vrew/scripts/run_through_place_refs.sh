#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <story-id> [comfy-model]" >&2
  exit 2
fi

story_id="$1"
comfy_model="${2:-${COMFYUI_MODEL:-z_image_turbo_bf16.safetensors}}"

if [[ ! -f "stories/${story_id}.txt" ]]; then
  echo "missing story file: stories/${story_id}.txt" >&2
  exit 1
fi

if [[ -n "${COMFYUI_API_KEY:-}" ]]; then
  comfy_url="${COMFYUI_URL:-https://cloud.comfy.org/api}"
  comfy_key_header="${COMFYUI_API_KEY_HEADER:-X-API-Key}"
  comfy_workflow="${COMFYUI_WORKFLOW_PATH:-}"
  echo "[INFO] using ComfyUI Cloud for place refs"
  echo "[INFO] comfy model: ${comfy_model}"
  if [[ -n "${comfy_workflow}" ]]; then
    echo "[INFO] comfy workflow override: ${comfy_workflow}"
  else
    echo "[INFO] comfy workflow: auto-select from model via yadam.cli"
  fi

  cmd=(
    python -m yadam.cli
    --story-id "${story_id}"
    --through-place-refs
    --non-interactive
    --image-api comfyui
    --image-model "${comfy_model}"
    --comfy-url "${comfy_url}"
    --comfy-api-key-header "${comfy_key_header}"
  )
  if [[ -n "${comfy_workflow}" ]]; then
    cmd+=(--comfy-workflow "${comfy_workflow}")
  fi
  "${cmd[@]}"
else
  echo "[WARN] COMFYUI_API_KEY is not set, fallback to gemini_flash_image"
  python -m yadam.cli --story-id "${story_id}" --through-place-refs --non-interactive --image-api gemini_flash_image
fi
