---
name: prompt_qc_flow
description: Use this skill when a story already has `work/<story-id>/out/project.json` and you want to validate/repair scene image prompts (`llm_clip_prompt` and `image.prompt_used`) for browser Gemini/Google Flow generation.
---

# prompt_qc_flow

Use this skill to run prompt quality control as a standalone stage, separate from pipeline execution.

## Goal

Validate and repair image prompts in `work/<story-id>/out/project.json` so they are stable for browser-based generation flows (`gemini`, `flow`) without API image generation.

## Scope

- Input:
  - `stories/<story-id>.txt`
  - `work/<story-id>/out/project.json`
- Primary target fields:
  - `scenes[].llm_clip_prompt`
  - `scenes[].image.prompt_used`
- Output:
  - updated `work/<story-id>/out/project.json`
  - optional reports under `work/<story-id>/out/`

## Workflow

1. Run style lock check (Ghibli 2D, non-photorealistic)
```bash
python skills/prompt_qc_flow/scripts/enforce_flow_style_lock.py --story-id <story-id>
```

2. Run prompt gate check
```bash
python skills/prompt_qc_flow/scripts/check_post_step8_prompt_gate.py --story-id <story-id>
```

3. Run suspicious prompt review
```bash
python skills/prompt_qc_flow/scripts/review_clip_prompts.py --story-id <story-id>
```

4. Run role/place/wardrobe-prop drift scan
```bash
python skills/prompt_qc_flow/scripts/scan_role_place_prop_drift.py --story-id <story-id>
```

This scan explicitly targets:
- Role drift:
  - who protects whom in confrontation beats
  - ledger/book holder ownership drift (`Shim` vs `Yeonhwa`)
- Place drift:
  - prompt location cues not matching `scene.places`
- Wardrobe/prop drift:
  - female `gat` risk
  - pregnancy context vs baby-in-arms conflict
  - character continuity anchors (e.g., Shim gaunt-face anchor, adjacent outfit/bandage continuity)

5. Run full script-vs-prompt role audit (all scenes)
```bash
python skills/prompt_qc_flow/scripts/audit_script_prompt_roles.py --story-id <story-id>
```

This full audit checks:
- explicit character mention mismatch between `scene.text` and `llm_clip_prompt`
- prompt mentioning characters outside `scene.characters`

6. Apply context continuity repair + style lock + drift locks (optional)
```bash
python skills/prompt_qc_flow/scripts/repair_clip_context_continuity.py --story-id <story-id> --apply
python skills/prompt_qc_flow/scripts/enforce_flow_style_lock.py --story-id <story-id> --apply
python skills/prompt_qc_flow/scripts/scan_role_place_prop_drift.py --story-id <story-id> --apply
```

7. Re-run style/gate/review/drift scan and role audit until all pass.

## Final-Tuning Mode (recommended before Flow generation)

When the project is already mostly stabilized, switch from "global rewrite" to "surgical repair":

1. Preserve good scenes
   - do not bulk-rewrite stable early/mid scenes
   - patch only explicitly flagged scenes and nearby continuity-dependent scenes
2. Fix only high-impact defects first
   - wrong `scene.characters` membership (extra/missing core actor)
   - wrong `scene.places` family (indoor/outdoor threshold mismatch)
   - malformed/truncated prompt text (broken substitution artifacts)
   - generic action placeholders that removed scene event meaning
3. Keep prompt fields aligned per patched scene
   - `llm_clip_prompt`
   - `image.prompt_used`
   - `image.prompt_original` (mirror final repaired wording for consistency)
4. Recompute metadata consistency after edits
   - `characters[].used_by_scenes`
   - `places[].used_by_scenes`
5. Run structure gate before leaving QC
```bash
python skills/make_vrew/scripts/check_structure_ready.py --story-id <story-id>
```

### Defect patterns to block (from latest production tuning)

- extra cast in frame despite `scene.text` not mentioning them
- broad exterior fallback for clearly indoor/threshold scenes
- role-weight drift (supporting character stealing the scene center)
- broken replacement artifacts in Korean text fragments, e.g.:
  - `...붙잡고 라며...`
  - `...을 떼고 을...`
- mood-only sentence used as `Visible action` (no drawable event)

### Minimal-surgery decision rule

- If a scene is already semantically correct and visually specific, leave it unchanged.
- If a scene fails in one dimension only (cast/place/action wording), edit that dimension only.
- Avoid "full-pass stylistic rewrites" in late stage, because they often reintroduce generic templates.

## Generalized guardrails (cross-story contamination prevention)

The skill now also audits and repairs these high-risk patterns:
- cross-story residue:
  - unknown proper nouns or non-cast names in prompts
  - wrong continuity lock targets (e.g., temple/Hanyang lock in non-temple scenes)
- over-templated actions:
  - repeated action sentences across many scenes
  - action-heavy script beats collapsed into generic movement templates
- emotion mis-insertion:
  - grief-heavy cues inserted into tension/stealth/confrontation beats
- script/prompt role grounding:
  - who acts, who protects, who holds key props, and place alignment

Run semantic audit directly:
```bash
python skills/prompt_qc_flow/scripts/audit_prompt_semantic_risks.py --story-id <story-id>
python skills/prompt_qc_flow/scripts/audit_prompt_semantic_risks.py --story-id <story-id> --apply
```

## Single-Lead Consistency Mode (optional)

When a story requires one fixed protagonist appearance across all scenes, run:

```bash
python skills/prompt_qc_flow/scripts/enforce_single_lead_consistency.py --story-id <story-id>
python skills/prompt_qc_flow/scripts/enforce_single_lead_consistency.py --story-id <story-id> --apply
```

This mode enforces:
- fixed 3-block prompt structure
- immutable style block
- immutable character fixed block
- immutable negative block
- periodic close-up insertion for face consistency

## One-shot command

```bash
skills/prompt_qc_flow/scripts/run_prompt_qc.sh <story-id> [--apply]
```

- default: check-only (no file changes)
- `--apply`: apply repairs, then re-run checks

## References

- `references/clip_prompt_review.md`
- `references/clip_prompt_repair.md`
- `references/prop_prompt_rules.json`
