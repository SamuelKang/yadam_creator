# File Shapes

## `work/<story-id>/out/project.json`

Relevant fields to update:

```json
{
  "project": {
    "phase": "structure_fixed",
    "phase_detail": "codex_structure_rules",
    "auto_scene_rules": {
      "variant_overrides": [],
      "scene_bindings": [],
      "notes": []
    }
  },
  "characters": [
    {
      "id": "char_001",
      "name": "홍길동",
      "aliases": ["길동", "홍 도령"],
      "species": "인간",
      "role": "주인공",
      "traits": [],
      "visual_anchors": [],
      "gender": "남",
      "age_stage": "청년",
      "age_hint": "",
      "variants": ["아동", "청년"],
      "context": "민간",
      "court_role": "",
      "social_class": "상민",
      "wealth_level": "빈곤",
      "wardrobe_tier": "T1",
      "wardrobe_anchors": [],
      "images": {},
      "image": {
        "status": "pending",
        "attempts": 0,
        "last_error": null,
        "path": null,
        "policy_rewrite_level": 0,
        "prompt_original": null,
        "prompt_used": null,
        "prompt_history": []
      }
    }
  ],
  "places": [
    {
      "id": "place_001",
      "name": "안채",
      "aliases": [],
      "visual_anchors": [],
      "image": {
        "status": "pending",
        "attempts": 0,
        "last_error": null,
        "path": null,
        "policy_rewrite_level": 0,
        "prompt_original": null,
        "prompt_used": null,
        "prompt_history": []
      }
    }
  ],
  "scenes": [
    {
      "id": 1,
      "chapter_no": 1,
      "chapter_title": "첫 장",
      "sentences": [],
      "text": "scene text",
      "characters": ["char_001"],
      "places": ["place_001"],
      "character_instances": [
        {
          "char_id": "char_001",
          "variant": "청년"
        }
      ],
      "llm_clip_prompt": "Wide shot, ...",
      "image": {
        "status": "pending",
        "attempts": 0,
        "last_error": null,
        "path": null,
        "policy_rewrite_level": 0,
        "prompt_original": null,
        "prompt_used": null,
        "prompt_history": []
      }
    }
  ]
}
```

Notes:

- Keep existing `images`, `image`, and scene image metadata unless the user asked to reset runtime state.
- `characters` and `places` inside each scene must use ids, not names.
- `character_instances` uses `char_id`, not canonical name.

## `stories/<story-id>_variant_overrides.yaml`

```yaml
variant_overrides:
  - story_id: story24
    character: 홍길동
    variant: 아동
    scenes: [1, 2, 3]
    chapter_title: ""
```

Use only for clear age/growth ranges.

## `stories/<story-id>_scene_bindings.yaml`

```yaml
scene_bindings:
  - story_id: story24
    scenes: [10, 11]
    chapter_title: ""
    mode: replace
    characters:
      - character: 홍길동
        variant: 청년
      - character: 월매
        variant: ""
    places:
      - 안채
```

Use only when a scene needs explicit continuity locks.
