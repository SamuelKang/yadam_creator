---
name: yadam-structure-rules
description: Use this skill when a yadam story text file already exists and the goal is to perform only the structure-and-rules phase: inspect `stories/storyNN.txt`, build or update structure data for characters/places/scenes/scene prompts, and create `stories/<story-id>_variant_overrides.yaml` and `stories/<story-id>_scene_bindings.yaml` for the later image pipeline.
---

# YADAM Structure + Rules

Use this skill when the user already has `stories/<story-id>.txt` and wants Codex to handle step 3 and step 4 only.

## Goal

Produce or update these outputs without running text generation or image generation:

- `work/<story-id>/out/project.json`
- `stories/<story-id>_variant_overrides.yaml`
- `stories/<story-id>_scene_bindings.yaml`

## Inputs

- Required: `stories/<story-id>.txt`
- Read if present:
  - `stories/<story-id>.synopsis`
  - `stories/<story-id>_variant_overrides.yaml`
  - `stories/<story-id>_scene_bindings.yaml`
  - `work/<story-id>/out/project.json`

## Workflow

1. Read `stories/<story-id>.txt` and identify the target `story-id`.
2. If `work/<story-id>/out/project.json` exists, inspect current `characters`, `places`, `scenes`, and `project.auto_scene_rules`.
3. Build or revise structure data:
   - canonical characters with aliases, species, role, age/variant, and visual anchors
   - canonical places with aliases and visual anchors
   - per-scene `characters`, `places`, `character_instances`
   - per-scene `llm_clip_prompt`
4. Generate only high-confidence continuity rules:
   - `variant_overrides` for clear age/growth zones
   - `scene_bindings` for scenes that need explicit character/place locks
5. Use only story-specific files under `stories/` for continuity rules.
6. Keep rules minimal. Do not invent names or places not supported by the story text.
7. After edits, sanity-check that:
   - every `scene_bindings.characters[].character` matches an existing canonical character name
   - every `scene_bindings.places[]` matches an existing canonical place name
   - `character_instances[].variant` uses an existing variant for that character, or empty string

## Output Rules

- Keep canonical names human-readable.
- If a real name exists, do not use a pure role label as canonical.
- Merge real name + role/호칭 into one character when they are the same person.
- Use `variants` instead of splitting one growth character into separate characters.
- `scene_prompts` must be short English clip prompts, with no quoted dialogue, no speech bubbles, no captions.
- Rules should be sparse. If no strong lock is needed, leave it out.

## File Shapes

Read `references/file_shapes.md` only when you need field-level guidance for `project.json` and rule YAMLs.

## When To Stop

Stop after structure/rules outputs are updated. Do not run image generation or `.vrew` export unless the user explicitly asks.
