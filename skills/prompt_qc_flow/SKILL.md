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
