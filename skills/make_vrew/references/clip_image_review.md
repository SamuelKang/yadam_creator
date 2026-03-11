# Clip Image Review

Use this reference after step 9 and before export.

## Goal

Catch suspicious clip outputs before `.vrew` export, especially clips that look blank, washed out, or overly white.

## Automatic Check

First run:

```bash
python skills/make_vrew/scripts/check_clip_images.py --story-id <story-id>
```

This should catch:

- `status != ok`
- missing clip file
- stale `_error.jpg`
- suspicious bright/white clip images

## Codex Visual Review

After the automatic check, Codex should inspect any suspicious clips and a few recent successful clips.

Priority checks:

- blank white background or mostly white frame
- lost background detail
- broken anatomy
- visible text, captions, subtitles, narration boxes, or speech bubbles
- obvious continuity break against character/place references

## If Problems Are Found

- Do not continue to export.
- Report the exact scene ids that failed review.
- Regenerate only the affected clips when possible.
- Re-run this review before export.
