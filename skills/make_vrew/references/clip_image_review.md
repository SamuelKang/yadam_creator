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
- repeated neighboring shots with the same centered pose, same expression, and nearly identical framing
- shadow/silhouette-only enemies when the script expects readable human attackers
- duplicated lead figures in one frame, including the same character appearing twice in foreground/background
- child/adult age drift or sudden costume swap across adjacent scenes
- reversed or self-pointing weapon handling, especially Joseon `ㄱ`-shaped sickles
- stretched or squashed aspect/proportions even when the file is technically 16:9
- palanquin scenes where the rider becomes a carrier, or wheels appear on a Joseon palanquin
- continuity against neighboring scenes and script state:
  - same hut room suddenly becoming a different courtyard or hall without a scripted transition
  - a sick, collapsed, tied, injured, or unconscious character suddenly standing, walking, or looking recovered
  - intimate 2-3 person scenes gaining unexplained extra people or losing a required character

For long runs of adjacent clips, generate and inspect a contact sheet first:

```bash
python3 scripts/make_contact_sheet.py --story-id <story-id> --scenes 7-11
```

## If Problems Are Found

- Do not continue to export.
- Report the exact scene ids that failed review.
- Regenerate only the affected clips when possible.
- Re-run this review before export.
