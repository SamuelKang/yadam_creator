# Structure Ready Review

Use this reference after step 5/6 and before step 7/8.

## Goal

Block character/place reference generation when the structure is still seed-quality or semantically wrong.

## Automatic Check

First run:

```bash
python skills/make_vrew/scripts/check_structure_ready.py --story-id <story-id>
```

This should catch:

- canonical character names stuck at generic role labels
- likely human characters mislabeled as animal species
- missing protagonist-grade human reference
- zero scene-level character coverage
- characters that exist but are never used by any scene

## Codex Review

If the automatic check fails, repair structure first.

Minimum repair targets:

- replace generic role labels with canonical names when the story clearly provides them
- move role labels to `aliases`
- set `species=인간` for human characters
- ensure the continuing protagonist and key supporting cast exist as character references
- ensure enough scenes have `characters` / `character_instances` for clip continuity

Do not continue to step 7/8 until this passes.
