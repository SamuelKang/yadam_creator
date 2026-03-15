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
- Do not rely on proper nouns alone; rewrite names into role/age/costume/action descriptions that an image model can draw without story context.
- Make the prompt standalone; remove cross-scene references like `same as before`, scene-number references, or chapter-title shorthand.
- When continuity matters, restate the needed visual anchor directly inside the prompt instead of referring backward.
- If a user reports a visual defect that auto-review missed, repair for that exact failure mode instead of only making the prompt longer.
- If the defect is really coming from structure or bindings, repair that before regeneration:
  - narrow or split `scene_bindings` when one recurring character is leaking into scenes where the script does not show them
  - correct `scene.characters` if the current cast list itself is wrong
- For adjacent early scenes, explicitly vary camera angle, body turn, hand action, and expression so the opening does not become repeated standing portraits.
- For ambush scenes, specify that attackers are readable human figures, not pure shadow silhouettes.
- For scenes with 2-3 named leads, explicitly state the exact cast and forbid duplicate copies of the same person in the frame.
- For child royalty continuity, restate child age and same robe/cape anchors when nearby scenes drift older or swap costume.
- For child lead continuity in general, restate small body scale, hat/headwrap, robe family, and any fresh injury/disguise anchor if nearby scenes have already drifted.
- For Joseon palanquin scenes, state that adult attendants carry a wheel-less palanquin and the child passenger does not carry it.
- For guard/bodyguard characters, replace passive wording like `stands beside him` or `watches tensely` with visible blocking such as shielding, crouching to inspect, half-drawing a sword, leaning close to warn, stepping in front, or scanning the surroundings.
- For continuity-heavy scenes, lock the state that must not drift:
  - keep the same room/background when neighboring scenes are one continuous beat
  - specify the exact required cast and exclude extra unexplained people when needed
  - specify whether a character is lying, collapsed, unconscious, kneeling, standing, or already recovering
  - specify whether the scene is still before treatment/relief or after it
  - specify whether a character has already switched from shaman/disguise/travel clothing into recovered noble attire or another post-event wardrobe
  - specify when a prop may contain natural in-world writing, but never ask for comic-style overlaid text, speech bubbles, or sound effects

## Good Repair Pattern

- from:
  - `Wide shot, Iseol and Bak Seobang hold tense silence on the road, grim resolve, no text.`
- to:
  - `wide shot, a twelve-year-old boy in a beige scholar robe walks a windy dirt road while his rugged middle-aged guard scans the brush with one hand near his sword, stone wall and fields behind them, wary tension, Joseon-era Korean webtoon style, no text`

## Completion Rule

After repairing flagged scenes:

1. Save `project.json`
2. Re-run:

```bash
python skills/make_vrew/scripts/review_clip_prompts.py --story-id <story-id>
```

3. Only continue to step 9 when the flagged review findings are resolved.
