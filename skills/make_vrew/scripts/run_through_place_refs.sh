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

python -m yadam.cli --story-id "${story_id}" --through-place-refs --non-interactive --image-api gemini_flash_image
