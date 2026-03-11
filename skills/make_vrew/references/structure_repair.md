# Structure Repair

Use this reference when `check_structure_ready.py` reports structure issues before step 7/8.

## Goal

Repair seed-quality character structure so character references are generated from usable canonical records.

## Repair Rules

### 1. Canonical character names

- Replace pure role labels with real canonical names when the story text clearly provides them.
- Move role labels to `aliases`.
- Examples:
  - `이설` should be canonical instead of `아들`, `소년`, `도련님`
  - `박 서방` should stay canonical if no fuller real name exists
  - `정조` should be canonical instead of `임금`, `전하`
  - `권 판관` may stay canonical if that is the story-stable identifier

### 2. Species correction

- If the character is a human role or named human, set `species=인간`.
- Only keep non-human species when the story explicitly supports it.
- Do not let weak seed hints override obvious human context.

### 3. Minimum cast

Before step 7/8, ensure the story has at least:

- one protagonist-grade human character reference
- major recurring supporting cast needed for clip continuity

For historical stories, this usually means protagonist + close ally + main antagonist + ruler/patron if recurring.

### 4. Scene character coverage

- Add `characters` and `character_instances` to scenes that clearly contain those characters.
- Keep it conservative, but do not leave scene character coverage near zero when the story is character-driven.

### 5. used_by_scenes

- After repairing scene character tags, refresh `used_by_scenes` so reference usage is accurate.

## If Bad Character Images Already Exist

If incorrect character references were already generated from bad structure:

- reset only the affected character images to `pending`
- clear stale paths and prompt history as needed
- regenerate step 7/8 after structure repair

## Validation

After repair:

1. rerun `check_structure_ready.py`
2. rerun `check_character_refs.py` after step 7/8
3. only then proceed to step 9
