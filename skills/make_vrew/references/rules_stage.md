# Rules Stage

Use this reference after structure merge is complete.

## Goal

Perform the role of the normal auto-rules LLM step, then apply the rules with Python.

## What Codex Must Produce

### `project.project.auto_scene_rules`

Shape:

```json
{
  "variant_overrides": [
    {
      "story_id": "story14",
      "character": "홍길동",
      "variant": "아동",
      "scenes": [1, 2, 3],
      "chapter_title": ""
    }
  ],
  "scene_bindings": [
    {
      "story_id": "story14",
      "scenes": [10, 11],
      "chapter_title": "",
      "mode": "replace",
      "characters": [
        {"character": "홍길동", "variant": "청년"}
      ],
      "places": ["안채"]
    }
  ],
  "notes": [
    "Only high-confidence continuity locks were added."
  ]
}
```

### Required story-specific YAML files

- `stories/<story-id>_variant_overrides.yaml`
- `stories/<story-id>_scene_bindings.yaml`

These are required outputs for step 6.
Treat them as the durable source of truth before starting step 7/8.
Write them whenever Codex has determined final continuity locks for the story.

## Rule Policy

- Generate only high-confidence rules.
- Prefer short contiguous ranges.
- Do not invent character or place names that are not already in canonical structure.
- Use `variant_overrides` only for clear age/growth phases.
- Use `scene_bindings` only when scene-level continuity drift is likely.
- Keep output minimal.

## Python Apply Step

After writing `project.project.auto_scene_rules` and both required story YAMLs, run:

```bash
python skills/make_vrew/scripts/apply_scene_rules.py --story-id <story-id>
```

This applies:

1. auto rules from `project.project.auto_scene_rules`
2. story-specific manual rule YAMLs
3. `used_by_scenes` refresh

## Before Step 7/8

Before running character/place reference generation:

1. Ensure both story-local YAML rules exist and match the intended final continuity locks.
2. Ensure `apply_scene_rules.py` has already been run successfully.
3. Only then run:

```bash
skills/make_vrew/scripts/run_through_place_refs.sh <story-id>
```

## Do Not Do

- Do not generate rules for every scene.
- Do not add weak speculative bindings.
- Do not skip the two story-local YAML files.
- Do not continue to image generation in this skill.
