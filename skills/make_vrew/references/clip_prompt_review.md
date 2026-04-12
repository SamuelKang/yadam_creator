# Clip Prompt Review

Use this reference after step 8 and before running step 9.

Mandatory first gate:

```bash
python skills/make_vrew/scripts/check_post_step8_prompt_gate.py --story-id <story-id>
python skills/make_vrew/scripts/review_clip_prompts.py --story-id <story-id>
python skills/make_vrew/scripts/repair_clip_context_continuity.py --story-id <story-id> --apply
python skills/make_vrew/scripts/check_post_step8_prompt_gate.py --story-id <story-id>
python skills/make_vrew/scripts/review_clip_prompts.py --story-id <story-id>
```

## Goal

Codex should review `scenes[].llm_clip_prompt` and remove prompt shapes that tend to create text, speech bubbles, dialogue-heavy images, or blank/white-background clips.
For browser-Flow runs, also review `scenes[].image.prompt_used` as the final generation prompt.

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
7. Catch likely continuity drift before any image generation:
   - broad `scene_bindings` that inject the wrong recurring character into a whole run
   - child lead prompts that stop restating child scale/headwear/costume and start drifting older
   - recovery or reveal scenes where the wardrobe should already have changed but the prompt still points back to the old look
8. Block static prompt language when scene text is dynamic:
   - avoid `tense stillness`, static standing phrasing, or portrait-like wording when the script beat includes running, pulling, tearing, shouting, or confrontation
9. Block clip prompts that use story-specific proper nouns directly.
10. Block Joseon prop-shape drift in continuity-critical prop beats:
   - `낫` scenes must not drift to western-scythe shape
   - `짚신` scenes must not drift to modern sandal wording
11. Block missing prop/state cues in script-critical beats:
   - palanquin travel beats must visibly include palanquin
   - blade-threat beats must visibly include blade proximity
   - seal/lining evidence beats must visibly include the evidence fragment
   - burning-evidence beats must visibly include flame/smoke
12. Block emotion-acting omissions:
   - when scene text carries fear/rage/grief/panic/relief beats, prompt must include readable facial expression and body gesture cues
13. For Google Flow `image.prompt_used`, enforce ordered video-prompt structure:
   - shot/camera
   - main subject(s)
   - visible action
   - environment
   - time/lighting/weather
   - wardrobe/prop continuity
   - style/mood
   - negative constraints
14. For Flow prompts, block templated filler language and require scene-text-grounded action:
   - block repeated generic templates that can apply to any scene
   - require at least one concrete visible action drawn from `scene.text`
15. Enforce prompt size target for Flow:
   - target 70-140 words per `image.prompt_used`
   - too short: under-specified, drift-prone
   - too long: diluted focus, unstable generation

## Rewrite Rules

- Prefer action and expression over spoken content.
- Replace spoken lines with facial expression, posture, hand gesture, gaze, and blocking.
- Do not assume the image model understands story-specific proper nouns.
- Replace character names with role + age + costume + physical anchor when useful.
- Make each prompt standalone:
  - the prompt should still make sense if the model has never seen the previous scene
  - avoid `same as before`, `same robe`, `scene 008`, or chapter-title references
- Review binding-driven cast continuity before generation:
  - compare the scene text, `scene.characters`, and any story-local `scene_bindings`
  - if an antagonist, magistrate, shaman, or other recurring lead is present only because a binding is too broad, fix the binding first rather than merely rewriting the prompt
- Keep shot cues if useful, but avoid bloated prompts.
- Avoid generic prompts like `Joseon-era dramatic scene` with no space/background detail.
- Include a concrete environment cue such as room, market, mountain path, hut interior, courtyard, prison cell, or village lane.
- Prefer drawable acting cues over abstract labels:
  - better: `the guard leans in and keeps one hand near his sword`
  - worse: `grim resolve`, `subtle pressure`, `holding tense silence`
- If scene text is emotionally strong, require explicit acting direction:
  - facial: eyes, jaw, brows, tears, breath
  - body: recoil, flinch, clenched posture, protective stance, abrupt turn, urgent hand gesture
- For recurring guard/bodyguard characters, make them do something visible in the frame instead of leaving them as a stiff bystander.
- For continuity-heavy runs, restate visual state changes directly:
  - bandaged arm
  - soot or burn marks
  - disguise on/off
  - noblewoman outfit after recovery
  - veil/staff removed after identity reveal
- When the user reports a repeated defect pattern, treat it as a prompt-stage blocker for all neighboring scenes with the same setup.
- For `낫` scenes, explicitly anchor Korean `ㄱ`/G-shaped sickle geometry with blade on inner corner.
- For `짚신` scenes, explicitly anchor traditional woven straw sandals and avoid modern sole/strap wording.
- Do not add modern objects, neon signage, printed lettering, or UI-like overlays.
- If the existing prompt is already clean and concise, leave it unchanged.

## Flow-Specific Quality Checks (`image.prompt_used`)

Before browser Flow generation, verify:

1. Grounding and tagging
   - `scenes[].characters` only includes people explicitly present in `scene.text`
   - `scenes[].places` matches direct scene cues (house/courtyard/magistrate/mountain/gorge)
   - no background contamination (e.g., house scene drifting to magistrate compound)
2. Shot-person consistency
   - no two-shot wording when only one person is present
   - no `exactly one` wording when scene text clearly has multiple people
3. Action specificity
   - replace abstract emotion labels with drawable movement/blocking
   - avoid static portrait phrasing in dynamic scenes
4. Continuity locks
   - if needed by scene, restate recurring anchors (same sickle shape, same outfit state, same hidden relic)
5. Style discipline
   - keep style layer shorter than scene action/environment content
   - keep Joseon-era Korean context explicit; avoid Japanese/Chinese costume drift
6. Negative constraints
   - include compact negatives only (no text/subtitles, no modern objects, no JP/CN costume drift, coherent anatomy)

Quick local checks (example):

```bash
python - <<'PY'
import json
d=json.load(open('work/<story-id>/out/project.json'))
ws=[len((s.get('image',{}).get('prompt_used','')).split()) for s in d['scenes']]
print('min',min(ws),'max',max(ws),'avg',round(sum(ws)/len(ws),1))
print('lt70',sum(w<70 for w in ws),'gt140',sum(w>140 for w in ws))
PY
```

## Good Direction

- `medium shot, a hungry girl grips the brass bowl with trembling hands in a dim Joseon room, oil-lamp glow, anxious eyes, Korean manhwa style`
- `wide shot, a twelve-year-old boy in a beige scholar robe walks a windy mountain path while his middle-aged guard scans the brush with one hand near his sword, Korean webtoon style`

## Bad Direction

- prompts with quoted speech
- prompts that mention captions or narration
- prompts asking for visible signs or written text
- prompts with no place tag and no environment cue
- generic standing-character prompts that can collapse into a white background
- prompts that depend on names alone, such as `Iseol confronts Bak Seobang`
- prompts that use abstract emotion labels without visible acting or blocking
