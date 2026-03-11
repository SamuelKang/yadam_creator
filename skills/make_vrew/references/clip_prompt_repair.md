# Clip Prompt Repair

Use this reference when `review_clip_prompts.py` reports `generic_prompt`, `missing_place_tag`, or `missing_environment_cue`.

## Goal

Before step 9, Codex should repair weak scene structure instead of merely stopping.

## What To Repair

For each flagged scene in `work/<story-id>/out/project.json`:

1. Add or correct `scene.places`
2. Rewrite `scene.llm_clip_prompt`

## Place Repair Rules

- Choose from existing canonical `places[]` only.
- Prefer one primary place id for the scene unless a second place is clearly needed.
- Infer the place from:
  - scene text
  - chapter title
  - neighboring scenes
  - already-established story-specific place usage
- Be conservative:
  - if the scene is indoors in the same chapter flow, prefer the current house/room place
  - if the scene is a travel/outdoor segment, prefer road/path/mountain/village-like place

## Prompt Repair Rules

- Keep it short English.
- Remove all direct dialogue and visible-text instructions.
- Add concrete environment cues.
- Add action/emotion/background detail.
- Keep Joseon setting explicit when useful.
- Prefer prompts that are visually generative, not generic labels.

## Good Repair Pattern

- from:
  - `Wide shot, Joseon-era dramatic scene, Korean faces, expressive emotion, no text.`
- to:
  - `wide shot, Yuni carries her exhausted younger brother on a dim mountain path at dusk, tangled brush, distant warm lamplight ahead, fear and urgency, Joseon-era Korean webtoon style, no text`

## Completion Rule

After repairing flagged scenes:

1. Save `project.json`
2. Re-run:

```bash
python skills/make_vrew/scripts/review_clip_prompts.py --story-id <story-id>
```

3. Only continue to step 9 when the flagged review findings are resolved.
