# Structure Merge

Use this reference after `run_through_tag_scene.sh` has created or updated `work/<story-id>/out/project.json`.

## Goal

Perform the role of the normal LLM extract step by replacing seed-only structure with richer Codex-reviewed structure.

## Update These Areas

### `project.llm_extract`

Record that Codex performed the extraction.

Example:

```json
{
  "enabled": true,
  "ok": true,
  "provider": "codex_skill",
  "mode": "manual_structure_extract",
  "notes": ["Codex enriched characters/places/scene tags/scene prompts after through-tag-scene run."]
}
```

### `characters`

Each character should include, when known:

- `id`
- `name`
- `aliases`
- `species`
- `role`
- `traits`
- `visual_anchors`
- `gender`
- `age_stage`
- `age_hint`
- `variants`
- `context`
- `court_role`
- `social_class`
- `wealth_level`
- `wardrobe_tier`
- `wardrobe_anchors`
- existing `images` and `image` metadata preserved if present

Use stable ids like `char_001`, `char_002`, in list order.

### `places`

Each place should include:

- `id`
- `name`
- `aliases`
- `visual_anchors`
- existing `image` metadata preserved if present

Use stable ids like `place_001`, `place_002`, in list order.

### `scenes`

For every existing scene, update:

- `characters`: list of character ids
- `places`: list of place ids
- `character_instances`: list of `{ "char_id": "...", "variant": "..." }`
- `llm_clip_prompt`: short English prompt

Preserve:

- `id`
- `chapter_no`
- `chapter_title`
- `sentences`
- `text`
- existing `image` metadata

## Decision Rules

- Prefer canonical real names over pure roles.
- Keep aliases for role/호칭 forms.
- If one person appears at multiple life stages, keep one canonical character and use `variants`.
- `character_instances.variant` should be empty unless the scene clearly indicates a specific stage.
- If a scene tag is uncertain, leave it conservative rather than inventing.
- If a clip prompt already exists and is good, keep it. Otherwise replace it with a better short English prompt.

## Clip Prompt Rules

- Short English only
- No quoted speech
- No speech bubbles
- No captions or visible text
- Include shot/action/emotion/background cues
- Preserve Joseon setting when relevant

## Do Not Do

- Do not run image generation
- Do not create rule YAMLs in this skill unless the user asks separately
- Do not delete runtime files unless the user explicitly asks
