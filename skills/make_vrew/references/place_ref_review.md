# Place Ref Review

Use this reference after step 7/8 and before step 9.

## Goal

Catch place reference problems before clip generation starts, and repair them if needed.

## Automatic Check

First run:

```bash
python skills/make_vrew/scripts/check_place_refs.py --story-id <story-id>
```

This should catch:

- `status != ok`
- missing image path
- missing image file
- stale `_error.jpg`

## Codex Visual Review

After the automatic check passes, Codex should visually inspect the place references that affect major scene runs.

Priority checks:

- place mood and style match the rest of the project
- no unwanted crowd/procession/extra figures in secluded places
- no modern artifacts, signage, visible text, or photo-like texture drift
- no style mismatch against other place references
- `used_by_scenes` heavy-use places should be checked first
- when using Comfy Cloud + Z-Image Turbo, prefer non-photoreal illustration/matte-painting tone
- for Joseon-era places, hard-block modern infrastructure:
  - utility poles, electric wires/cables, street lamps, traffic signs, cars, asphalt roads

Examples:

- `산길`: no bystanders, no procession, no crowd; should feel isolated
- `읍내 시장`: crowd allowed, but avoid over-detailed semi-realistic style drift
- `박 노인의 오두막`: maintain Joseon hut/ondol mood, not barn-like
- `마을`: reject frames with visible power poles/wires even if overall composition is good

## If Problems Are Found

- Do not continue to step 9.
- Repair the place before continuing.

Repair flow:

1. Update the place record in `project.json`
   - refine `visual_anchors`
   - if style drifted to photoreal, add explicit non-photoreal anchor and modern-artifact exclusion cues
   - keep canonical place id/name stable
2. Reset that place image to `pending`
3. Delete the stale place image/error file if needed
4. Identify dependent scenes from `used_by_scenes`
5. Reset only those clip images to `pending`
6. Re-run step 7/8 for the place reference
7. Re-run step 9 only for affected clips

## Completion Rule

Only continue to step 9 when place references are visually consistent and semantically correct.
