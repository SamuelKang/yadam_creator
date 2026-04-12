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
  echo "[INFO] COMFYUI_API_KEY is set but ignored: make_vrew now uses Gemini API."
fi

echo "[INFO] using Gemini API for place refs"
python -m yadam.cli --story-id "${story_id}" --through-place-refs --non-interactive --image-api gemini_flash_image
