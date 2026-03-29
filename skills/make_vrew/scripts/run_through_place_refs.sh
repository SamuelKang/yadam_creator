#!/bin/zsh
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <story-id>" >&2
  exit 2
fi

story_id="$1"

if [[ ! -f "stories/${story_id}.txt" ]]; then
  echo "missing story file: stories/${story_id}.txt" >&2
  exit 1
fi

if [[ -n "${COMFYUI_API_KEY:-}" ]]; then
  comfy_url="${COMFYUI_URL:-https://cloud.comfy.org/api}"
  comfy_key_header="${COMFYUI_API_KEY_HEADER:-X-API-Key}"
  comfy_workflow="${COMFYUI_WORKFLOW_PATH:-yadam/config/comfy_workflows/yadam_api_z_image_turbo_placeholders.json}"
  echo "[INFO] using ComfyUI Cloud + Z-Image Turbo for place refs"
  python -m yadam.cli \
    --story-id "${story_id}" \
    --through-place-refs \
    --non-interactive \
    --image-api comfyui \
    --image-model z_image_turbo_bf16.safetensors \
    --comfy-url "${comfy_url}" \
    --comfy-api-key-header "${comfy_key_header}" \
    --comfy-workflow "${comfy_workflow}"
else
  echo "[WARN] COMFYUI_API_KEY is not set, fallback to gemini_flash_image"
  python -m yadam.cli --story-id "${story_id}" --through-place-refs --non-interactive --image-api gemini_flash_image
fi
