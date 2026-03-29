# YADAM CLI 사용설명서

## 1. 개요

`yadam.cli`는 아래 흐름을 실행합니다.

1. 시놉시스 생성
2. 스토리(대본) 생성
3. 이미지 생성 + `.vrew` export

기본 실행은 interactive 모드이며, 단계별 확인을 받습니다.

## 2. 기본 명령

### 전체 파이프라인 실행

```bash
python -m yadam.cli --story-id story13
```

### 시놉시스만 생성

```bash
python -m yadam.cli --story-id story13 --make_synopsis
```

### 스토리만 생성

```bash
python -m yadam.cli --story-id story13 --make-story
python -m yadam.cli --story-id story13 --make-story 1000
```

### 제목부터 새 storyNN 자동 생성

```bash
python -m yadam.cli --title "제목 또는 훅 문구"
```

## 3. 주요 옵션

- `--story-id storyNN`: 대상 스토리 ID 지정
- `--title "..."`: 새 `stories/storyNN.title` 생성 후 파이프라인 시작
- `--make_synopsis`: `title -> synopsis`만 실행
- `--make-story [500|1000]`: `synopsis -> story`만 실행
- `--llm-model <model>`: 텍스트 LLM 오버라이드. 기본값은 `gemini-3-flash-preview`
- `--image-api {vertex_imagen|gemini_flash_image|comfyui}`: 이미지 백엔드 선택
- `--image-model <model>`: 이미지 모델 오버라이드
- `--non-interactive`: 확인 없이 끝까지 자동 진행
- `--clean-workdir`: `work/<story-id>/` 삭제 후 재생성
- `--through-tag-scene`: 대본 정규화, scene 분할, seed 추출, `tag_scene`까지만 수행
- `--through-place-refs`: 캐릭터/장소 레퍼런스 이미지(7/8단계)까지만 수행
- `--through-clips`: clip 이미지 생성(9단계)까지만 수행
- `--vrew-clip-max-chars <N>`: `.vrew` 자막 분할 길이

## 4. 텍스트 LLM 모델 선택

`--llm-model`은 텍스트 생성/분석 계열 LLM에 공통 적용됩니다.

- 적용 대상:
  - synopsis 생성
  - story chapter 생성
  - scene prompt 생성
  - prompt rewrite
  - scene binding
  - entity extract
- 기본값: `gemini-3-flash-preview`
- 미지정 시 위 기본값을 사용합니다.
- 이미지 모델은 별개입니다. 이미지 쪽은 `--image-api`, `--image-model`로 제어합니다.

예시:

```bash
# 기본 텍스트 LLM 사용
python -m yadam.cli --story-id story13

# 텍스트 LLM만 명시적으로 지정
python -m yadam.cli --story-id story13 --llm-model gemini-3-flash-preview

# LLM 구조 추출 전까지만 실행
python -m yadam.cli --story-id story13 --through-tag-scene

# 캐릭터/장소 레퍼런스까지만 실행
python -m yadam.cli --story-id story13 --through-place-refs

# clip 생성까지만 실행
python -m yadam.cli --story-id story13 --through-clips

# 텍스트 LLM + Gemini 이미지 모델을 함께 지정
python -m yadam.cli \
  --story-id story13 \
  --llm-model gemini-3-flash-preview \
  --image-api gemini_flash_image \
  --image-model gemini-2.5-flash-image
```

## 5. Interactive 확인 입력 규칙

일부 확인 프롬프트에서 아래 입력을 받습니다.

- `Y` 또는 Enter: 진행
- `n`: 해당 단계 중단/스킵
- `a`: 이후 모든 단계를 non-interactive로 자동 진행

참고:

- `덮어쓸까요? (y/n)`에서 `n`을 누르면 기존 파일을 유지하고 계속 진행합니다.
- `시놉시스 생성 후 story 진행` 질문에서 `n`을 누르면 story 생성만 건너뜁니다.
- 이때 기존 `stories/<story-id>.txt`가 있으면 이미지 단계로 진행하고, 없으면 종료됩니다.

## 6. 이미지 API별 준비사항

### Gemini Flash Image

```bash
export GOOGLE_API_KEY="YOUR_API_KEY"
python -m yadam.cli --story-id story13 --image-api gemini_flash_image
```

### Vertex Imagen

ADC(gcloud application-default login) + Vertex 환경변수가 필요합니다.

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="YOUR_GCP_PROJECT"
export GOOGLE_CLOUD_LOCATION="us-central1"
python -m yadam.cli --story-id story13 --image-api vertex_imagen
```

### ComfyUI

```bash
python -m yadam.cli \
  --story-id story13 \
  --image-api comfyui \
  --image-model z_image_turbo_bf16.safetensors \
  --comfy-url http://127.0.0.1:8188
```

ComfyUI Cloud 예시:

```bash
python -m yadam.cli \
  --story-id story13 \
  --image-api comfyui \
  --image-model z_image_turbo_bf16.safetensors \
  --comfy-url https://cloud.comfy.org/api \
  --comfy-api-key \"$COMFYUI_API_KEY\" \
  --comfy-api-key-header X-API-Key \
  --comfy-workflow yadam/config/comfy_workflows/yadam_api_z_image_turbo_placeholders.json
```

Comfy 모델 선택 규칙:
- 기본 모델: `z_image_turbo_bf16.safetensors`
- 모델 오버라이드: `--image-model <model>`
- 워크플로 미지정 시 모델명으로 자동 선택:
  - `z_image`/`z-image` 포함 -> `yadam_api_z_image_turbo_placeholders.json`
  - `flux` 포함 -> `yadam_api_flux_schnell_base_placeholders.json`
  - 그 외 -> `yadam_api_sdxl_base_fast_placeholders.json`

워크플로 템플릿:
- `yadam/config/comfy_workflows/yadam_api_z_image_turbo_placeholders.json`
- `yadam/config/comfy_workflows/yadam_api_z_image_base_placeholders.json`
- `yadam/config/comfy_workflows/yadam_api_flux_schnell_base_placeholders.json`
- `yadam/config/comfy_workflows/yadam_api_flux_schnell_consistency_placeholders.json`
- `yadam/config/comfy_workflows/yadam_api_flux_schnell_fallback_placeholders.json`

운영 노하우/장애 대응/모델 선별 기준:
- `docs/comfy_cloud_playbook.md`

## 7. 자주 쓰는 실행 예시

```bash
# 기본(단계별 확인)
python -m yadam.cli --story-id story13

# 확인 없이 전체 자동
python -m yadam.cli --story-id story13 --non-interactive

# tag_scene까지만 실행하고 중단
python -m yadam.cli --story-id story13 --through-tag-scene

# 캐릭터/장소 레퍼런스까지만 실행하고 중단
python -m yadam.cli --story-id story13 --through-place-refs

# Gemini Flash Image로 전체 실행
python -m yadam.cli --story-id story13 --image-api gemini_flash_image

# 텍스트 LLM을 명시적으로 지정
python -m yadam.cli --story-id story13 --llm-model gemini-3-flash-preview

# 확인 없이 Gemini Flash Image로 전체 자동
python -m yadam.cli --image-api gemini_flash_image --non-interactive --story-id story13 

# work 디렉터리 초기화 후 재실행
python -m yadam.cli --story-id story13 --clean-workdir
```

## 8. 장면-인물/장소 고정 규칙(자동 + 수동)

파이프라인는 구조 단계 이후 아래 순서로 장면 규칙을 적용합니다.

1. LLM 자동 규칙 생성 (`project.project.auto_scene_rules` 저장)
2. 수동 규칙 파일 적용
   - `stories/<story-id>_variant_overrides.yaml`, `stories/<story-id>_scene_bindings.yaml`
3. `characters[].used_by_scenes`, `places[].used_by_scenes` 자동 갱신

### 수동 규칙 파일

- `stories/<story-id>_variant_overrides.yaml` (권장)
  - 특정 character variant(아동/청소년/청년 등)을 scene 범위에 강제
- `stories/<story-id>_scene_bindings.yaml` (권장)
  - 특정 scene 범위에 등장 인물/장소를 `replace` 또는 `add` 방식으로 고정

### scene_bindings 예시

```yaml
scene_bindings:
  - story_id: story24
    scenes: 16-20
    mode: replace
    characters:
      - character: 김도령 현우
        variant: ""
      - character: 시어머니
        variant: ""
    places:
      - 안채 대청마루
```

## 9. 이름-이미지 매핑 점검(Story14: "박 노인" 사례)

`story14`에서 텍스트에 `"박 노인"`이 있을 때, 파이프라인이 `char_004_박_노인_노년.jpg`를 참조하도록 점검/운영 기준을 아래처럼 둡니다.

### 점검 결과 요약

- `characters`에 `id=char_004`, `name=박 노인`, `variants=[노년]` 존재
- `characters[].images["노년"].path`와 `characters[].image.path`가 모두
  `work/story14/characters/char_004_박_노인_노년.jpg`로 연결
- scene 텍스트에 `"박 노인"`이 있는 구간에서 `scene.characters`와 `scene.character_instances`에 `char_004`가 포함됨

### 코드 동작 기준

- 이름 매핑:
  - `orchestrator._apply_scene_bindings()`에서 `char_name_to_id`를 생성할 때 `str(name).strip()` 기준으로 이름→`char_id` 매핑
  - `resolve_char_entry()`가 입력값을 `char_id` 우선, 없으면 이름으로 해석
- 클립 참조 이미지 선택:
  - `scene.character_instances.variant`가 있으면 `characters[].images[variant].path`를 우선 사용
  - variant가 없으면 `characters[].image.path`로 fallback
  - 따라서 `"박 노인"`은 `노년` variant 이미지(`char_004_박_노인_노년.jpg`)를 안정적으로 참조

### 빠른 확인 명령

```bash
# char_004 메타/이미지 경로 확인
python3 - <<'PY'
import json
d=json.load(open("work/story14/out/project.json"))
for c in d.get("characters",[]):
    if c.get("id")=="char_004":
        print(c["name"], c.get("variants"))
        print(c.get("images",{}).get("노년",{}).get("path"))
        print(c.get("image",{}).get("path"))
        break
PY

# scene에 char_004 연결 여부 확인
python3 - <<'PY'
import json
d=json.load(open("work/story14/out/project.json"))
for s in d.get("scenes",[]):
    if "박 노인" in (s.get("text") or ""):
        print(s["id"], s.get("characters"), s.get("character_instances"))
PY
```
