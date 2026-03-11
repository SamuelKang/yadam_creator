# Character Ref Review

Use this reference after step 7/8 and before step 9.

## Goal

Catch character reference problems before clip generation starts.

## Automatic Checks

First run:

```bash
python skills/make_vrew/scripts/check_character_refs.py --story-id <story-id>
```

This should catch:

- `status != ok`
- missing image path
- missing image file
- stale `_error.jpg` alongside an `ok` image

## Codex Visual Review

After the automatic check passes, Codex should visually inspect the key character references that matter for continuity.

Priority checks:

- age/variant matches the story lock
  - example: `윤이(청소년)` vs `윤이(청년)`
  - example: `칠성이(아동)` vs `칠성이(청년)`
  - example: `박 노인(노년)`
- at least one clear protagonist-grade reference exists when the story has a continuing main character
- canonical names are not stuck at generic labels like `아들`, `아버지`, `스님`, `나리` when a real named character should exist
- a likely human protagonist has not been misclassified as an animal species
- canonical name matches the correct image file/path
- face, hair, and outfit anchors are stable enough for clip reference use
- no visible text, subtitles, captions, or speech bubbles
- no major anatomy breakage

## If Problems Are Found

- Do not continue to step 9.
- Report the exact character or variant that failed review.
- Separate the problem type:
  - metadata/path issue
  - continuity/variant issue
  - visual quality issue
  - structure issue (missing protagonist reference, generic canonical names, species mismatch)
- For metadata/path issues:
  - fix `project.json` or stale files without regeneration if possible
- For structure issues:
  - repair step-5 structure first so the main character exists as a canonical reference before clip generation
- For visual quality issues:
  - mark only the affected character/variant for regeneration and rerun step 7/8
- After fixes, rerun this review before step 9.
