# Clip Prompt Review

Use this reference after step 8 and before running step 9.

## Goal

Codex should review `scenes[].llm_clip_prompt` and remove prompt shapes that tend to create text, speech bubbles, dialogue-heavy images, or blank/white-background clips.

## Review Priorities

1. Remove direct quoted dialogue.
2. Remove `Name: ...` or role-label dialogue fragments.
3. Remove words that ask for visible text or imply it:
   - speech bubble
   - caption
   - subtitle
   - narration box
   - text overlay
   - visible text
   - quote marks
4. Keep the prompt as a short English visual description.
5. Preserve Joseon period context and scene continuity.
6. Ensure the scene has a concrete place tag or at least a strong environment cue before step 9.

## Rewrite Rules

- Prefer action and expression over spoken content.
- Replace spoken lines with facial expression, posture, hand gesture, gaze, and blocking.
- Keep shot cues if useful, but avoid bloated prompts.
- Avoid generic prompts like `Joseon-era dramatic scene` with no space/background detail.
- Include a concrete environment cue such as room, market, mountain path, hut interior, courtyard, prison cell, or village lane.
- Do not add modern objects, neon signage, printed lettering, or UI-like overlays.
- If the existing prompt is already clean and concise, leave it unchanged.

## Good Direction

- `medium shot, Yuni grips the brass bowl with trembling hands in a dim Joseon room, oil-lamp glow, anxious resolve, Korean manhwa style`
- `wide shot, two children stand on a windy mountain path at dusk, worn Joseon clothes, distant village lights, loneliness and tension, Korean webtoon style`

## Bad Direction

- prompts with quoted speech
- prompts that mention captions or narration
- prompts asking for visible signs or written text
- prompts with no place tag and no environment cue
- generic standing-character prompts that can collapse into a white background
