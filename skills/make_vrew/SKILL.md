---
name: make_vrew
description: Use this skill when the user provides a yadam `story-id` such as `story14` and wants to run the Python preprocessing path through `tag_scene`, then have Codex perform the step-5/6 LLM roles, review clip prompts, and run image generation through step 9.
---

# make_vrew

Use this skill when the user already has `stories/<story-id>.txt` and wants a hybrid flow:

1. Run Python preprocessing through `tag_scene`
2. Then have Codex perform the step-5 LLM role manually
3. Then have Codex perform step 6 and persist final continuity rules in story-local YAML files
4. Then verify the structure is actually ready for character references
5. Then run only character/place reference generation through step 8
6. Then run character reference review and stop if problems are found
7. Then run place reference review and repair if needed
8. Then have Codex review and repair scene clip prompts before step 9
9. Then run clip generation through step 9
10. Then review clip images and stop if suspicious clips are found
11. If step 9 finishes with all clips successful, run Python export
12. Then automatically check image errors and report them to the user

The skill should stop before `.vrew` export only if clip generation is incomplete or has errors.

## Python Stage

First run the pipeline only through:

- script load and normalization
- hash/reuse check
- sentence split
- chapter attach
- scene split
- seed character/place extraction
- `tag_scene`

Run:

```bash
skills/make_vrew/scripts/run_through_tag_scene.sh <story-id>
```

Example:

```bash
skills/make_vrew/scripts/run_through_tag_scene.sh story14
```

## Codex LLM Stage

After the Python stage completes, Codex must perform the role that `LLMEntityExtractor.extract(...)` normally performs.

Update `work/<story-id>/out/project.json` so that it contains:

- canonical `characters`
- canonical `places`
- scene-level `characters`
- scene-level `places`
- scene-level `character_instances`
- scene-level `llm_clip_prompt`
- `project.llm_extract` metadata describing that Codex performed the extraction

Read `references/structure_merge.md` when updating `project.json`.

## Step 6 Rules Stage

After structure merge, Codex must also perform step 6.

1. Create or update `project.project.auto_scene_rules` inside `work/<story-id>/out/project.json`
2. Create or update these story-local rule files:
   - `stories/<story-id>_variant_overrides.yaml`
   - `stories/<story-id>_scene_bindings.yaml`
3. Apply those rules by running:

```bash
python skills/make_vrew/scripts/apply_scene_rules.py --story-id <story-id>
```

Read `references/rules_stage.md` when generating step-6 rule content.

## Step 7/8 Reference Stage

After step 6 is complete:

1. Ensure these required story-local rule files exist and reflect the final intended continuity state:
   - `stories/<story-id>_variant_overrides.yaml`
   - `stories/<story-id>_scene_bindings.yaml`
2. Before any reference generation, run:

```bash
python skills/make_vrew/scripts/check_structure_ready.py --story-id <story-id>
```

3. If this check fails, do not stop at reporting only. Codex must repair the step-5 structure in `project.json` first, using `references/structure_repair.md`.
4. Rerun `check_structure_ready.py` until it passes.
5. Then run only character/place reference generation:

```bash
skills/make_vrew/scripts/run_through_place_refs.sh <story-id>
```

This must stop after step 8. It must not continue into clip generation or export.

## Character Reference Review Stage

Before step 9, character references must pass both automatic checks and Codex review.

First run:

```bash
python skills/make_vrew/scripts/check_character_refs.py --story-id <story-id>
```

Then review the generated character images using `references/character_ref_review.md`.

If any issue is found:

- do not continue to step 9
- report the exact character or variant that failed
- distinguish metadata/path issues from visual continuity issues
- also treat missing protagonist-grade references, generic canonical names, or human/animal species mismatches as hard blockers
- regenerate only the affected character/variant when regeneration is needed
- rerun this review before continuing

Only continue to step 9 when character references are clean enough for clip reference use and the story has a usable protagonist/reference set for face continuity.

## Place Reference Review Stage

Before step 9, place references must pass both automatic checks and Codex review.

First run:

```bash
python skills/make_vrew/scripts/check_place_refs.py --story-id <story-id>
```

Then review the generated place images using `references/place_ref_review.md`.

If any issue is found:

- do not continue directly to step 9
- repair the place record in `project.json`
- regenerate the affected place reference
- identify `used_by_scenes` and reset only affected clips
- rerun the place review before continuing

Only continue to step 9 when place references are visually consistent and semantically correct.

## Step 9 Prompt Review Stage

Before step 9, Codex must review `scenes[].llm_clip_prompt` inside `work/<story-id>/out/project.json`.

First run:

```bash
python skills/make_vrew/scripts/review_clip_prompts.py --story-id <story-id>
```

Then Codex must fix suspicious prompts directly in `project.json`.

If review finds missing place tags, generic prompts, or missing environment cues, Codex must repair the scene structure before step 9 instead of just stopping.

Read `references/clip_prompt_repair.md` when repairing flagged scenes.

Read `references/clip_prompt_review.md` when reviewing prompts.

Minimum review requirements:

- remove quoted dialogue
- remove `Name: ...` dialogue fragments
- remove any speech bubble, caption, subtitle, narration-box, or visible-text wording
- reject generic prompts that do not ground the scene in a concrete environment
- reject scenes that still have no usable place tag or environment cue
- keep prompts short English scene descriptions
- preserve Joseon setting and current scene continuity

## Step 9 Clip Stage

After prompt review is complete, run:

```bash
skills/make_vrew/scripts/run_through_clips.sh <story-id>
```

This must stop after step 9. It must not continue into export.

## Error Check Stage

After step 9 finishes, always run:

```bash
python skills/make_vrew/scripts/show_image_errors.py --story-id <story-id> --include-clips
```

If any character/place/clip image errors exist, report them to the user immediately with:

- object type
- label
- status
- attempts
- last error

If no errors exist, say so briefly.

## Clip Image Review Stage

After step 9 and before export, run:

```bash
python skills/make_vrew/scripts/check_clip_images.py --story-id <story-id>
```

Then review suspicious clips using `references/clip_image_review.md`.

If any suspicious clip issues are found:

- do not continue to export
- report the exact scene ids
- treat them as clip regeneration targets
- rerun clip review after regeneration

## Export Stage

If step 9 finishes with no clip errors and clip image review is clean, run:

```bash
skills/make_vrew/scripts/run_export_after_clips.sh <story-id>
```

This should reuse existing story/structure/reference/clip artifacts and let Python perform the normal export stage.

If any clip errors or suspicious clip review findings remain, do not run export.

## Inputs

- Required: `story-id` like `story14`
- Required file: `stories/<story-id>.txt`
- Read if present:
  - `stories/<story-id>.synopsis`
  - `work/<story-id>/out/project.json`

## Checks

Before running:

1. Confirm `stories/<story-id>.txt` exists.
2. If missing, stop and report the missing file.

After running:

1. Report whether the command succeeded.
2. Confirm `work/<story-id>/out/project.json` exists.
3. Update that file with Codex-generated structure data.
4. Generate both required story-local step-6 rule files and apply them with `apply_scene_rules.py`.
5. Run `check_structure_ready.py` before step 7/8 and repair structure instead of merely stopping if it fails.
6. Rerun the structure check until it passes.
7. Run step 7/8 only through `run_through_place_refs.sh`.
8. Run `check_character_refs.py` and perform character image review before step 9.
9. If character reference issues exist, repair structure or regenerate only affected references instead of entering step 9.
10. Run `check_place_refs.py` and perform place image review before step 9.
11. If place reference issues exist, repair the place, regenerate it, reset dependent clips, and rerun the review before step 9.
12. Review `llm_clip_prompt` before step 9, repair flagged scenes in `project.json`, rerun the review until clean, then run step 9 only through `run_through_clips.sh`.
13. Run `show_image_errors.py --include-clips` automatically and report the result to the user.
14. Run `check_clip_images.py` and review suspicious clips before export.
15. If clip image review finds issues, stop and report clip regeneration targets.
16. If there are no clip errors and no suspicious clip review findings, run export through `run_export_after_clips.sh`.
17. If any clip errors remain, stop before export and report the errors.

## Output Rules

- Keep canonical names human-readable.
- If a real name exists, do not use a pure role label as canonical.
- Merge real name + role/호칭 into one character when they are the same person.
- Use `variants` instead of splitting one growth character into separate characters.
- `llm_clip_prompt` must be short English clip prompt text with no quoted dialogue, no speech bubbles, no captions, and no explicit visible text.
- Scene `characters` and `places` must use ids, not names.
- `character_instances` must use `char_id` and `variant`.
- Preserve existing runtime image metadata unless the user explicitly asks to reset it.
- Treat story-local YAML rules as the required durable source of truth for step 6 before starting step 7/8.
