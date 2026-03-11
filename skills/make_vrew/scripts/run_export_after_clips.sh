#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <story-id>" >&2
  exit 2
fi

story_id="$1"
root="$(cd "$(dirname "$0")/../../.." && pwd)"
story_path="$root/stories/${story_id}.txt"

if [[ ! -f "$story_path" ]]; then
  echo "missing story file: $story_path" >&2
  exit 1
fi

cd "$root"
python -m yadam.cli --story-id "$story_id" --non-interactive --image-api gemini_flash_image
