# Comfy Cloud Playbook (Yadam)

이 문서는 `yadam`에서 Comfy Cloud를 안정적으로 운용하기 위한 실무 노하우를 정리한다.

## 1) 목적과 범위
- 대상: `--image-api comfyui` + Comfy Cloud(`https://cloud.comfy.org/api`) 경로
- 목표:
  - 워크플로/모델 미스매치로 인한 실패 감소
  - 캐릭터 시트(전신, 무배경, 무텍스트, 고증 유지) 품질 안정화
  - 재현 가능한 실행 절차 확보

## 2) 기본 환경
- 비밀값 파일: 저장소 루트 `.comfyui.env` (git 제외)
- 기본 로드:
```bash
set -a; source .comfyui.env; set +a
```
- 권장 변수:
```bash
COMFYUI_URL='https://cloud.comfy.org/api'
COMFYUI_API_KEY='...'
COMFYUI_API_KEY_HEADER='X-API-Key'
```

## 3) Cloud API 핵심 엔드포인트
- 워크플로 제출: `POST /api/prompt`
- 현재 프롬프트 실행 정보: `GET /api/prompt`
- 워크플로 템플릿 목록: `GET /api/workflow/templates`
- 서브그래프 블루프린트 목록: `GET /api/workflow/blueprints`
- 특정 블루프린트 조회: `GET /api/workflow/blueprints/{id}`
- 노드 정보 전체: `GET /api/object_info`
- 서버 feature flags: `GET /api/features`
- 잡 상태/결과: `GET /api/jobs/{prompt_id}`
- 잡 목록: `GET /api/jobs`
- 잡 목록(페이지/필터): `GET /api/jobs/list`
- 큐 정보: `GET /api/queue`
- 큐 관리(삭제/정리): `POST /api/queue`
- 실행 중 인터럽트: `POST /api/interrupt`
- 실행 히스토리 조회(v2): `GET /api/history2`
- 특정 prompt 히스토리: `GET /api/history/{prompt_id}`
- 실행 히스토리 관리(삭제): `POST /api/history`
- 모델 폴더 목록: `GET /api/experiment/models`
- 폴더 내 모델: `GET /api/experiment/models/{folder}`
- 모델 프리뷰: `GET /api/experiment/models/preview/{folder}/{path_index}/{filename}`
- 파일 뷰: `GET /api/view?...`

참고:
- https://docs.comfy.org/development/cloud/overview
- https://docs.comfy.org/development/cloud/api-reference
- https://docs.comfy.org/development/cloud/openapi
- https://docs.comfy.org/api-reference/cloud/workflow/get-information-about-current-prompt-execution
- https://docs.comfy.org/api-reference/cloud/workflow/submit-a-workflow-for-execution
- https://docs.comfy.org/api-reference/cloud/workflow/get-available-workflow-templates
- https://docs.comfy.org/api-reference/cloud/workflow/get-available-subgraph-blueprints
- https://docs.comfy.org/api-reference/cloud/workflow/get-a-specific-subgraph-blueprint
- https://docs.comfy.org/api-reference/cloud/node/get-all-node-information
- https://docs.comfy.org/api-reference/cloud/node/get-server-feature-flags
- https://docs.comfy.org/api-reference/cloud/job/manage-execution-history
- https://docs.comfy.org/api-reference/cloud/job/get-execution-history-v2
- https://docs.comfy.org/api-reference/cloud/job/get-history-for-specific-prompt
- https://docs.comfy.org/api-reference/cloud/job/list-jobs-with-pagination-and-filtering
- https://docs.comfy.org/api-reference/cloud/job/get-full-job-details
- https://docs.comfy.org/api-reference/cloud/job/get-queue-information
- https://docs.comfy.org/api-reference/cloud/job/manage-queue-operations
- https://docs.comfy.org/api-reference/cloud/job/interrupt-currently-running-jobs
- https://docs.comfy.org/api-reference/cloud/job/get-job-status
- https://docs.comfy.org/api-reference/cloud/model/get-models-in-a-specific-folder
- https://docs.comfy.org/api-reference/cloud/model/get-model-preview-image

## 3.1) Workflow API 빠른 사용 예시
```bash
# 공통
set -a; source .comfyui.env; set +a
BASE_URL="${COMFYUI_URL:-https://cloud.comfy.org/api}"
AUTH_HEADER="${COMFYUI_API_KEY_HEADER:-X-API-Key}"

# 1) 현재 프롬프트 실행 정보
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/prompt" | jq .

# 2) 워크플로 제출
curl -sS -X POST \
  -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": $(cat workflow_api.json)}" \
  "$BASE_URL/prompt" | jq .

# 3) 워크플로 템플릿 목록
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/workflow/templates" | jq .

# 4) 블루프린트 목록
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/workflow/blueprints" | jq .

# 5) 특정 블루프린트 조회 (id는 목록 결과에서 선택)
BP_ID="..."
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/workflow/blueprints/$BP_ID" | jq .

# 6) 노드 스키마(입력키/타입) 전체 조회
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/object_info" | jq .

# 7) 서버 feature flags 확인
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/features" | jq .

# 8) 큐 상태 확인
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/queue" | jq .

# 9) 잡 목록(페이지/필터)
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/jobs/list?page=1&page_size=20&status=completed" | jq .

# 10) 잡 상세 조회
JOB_ID="..."
curl -sS -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  "$BASE_URL/jobs/$JOB_ID" | jq .

# 11) 실행 중 인터럽트
curl -sS -X POST \
  -H "$AUTH_HEADER: $COMFYUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$BASE_URL/interrupt" | jq .
```

운영 팁:
- 템플릿/블루프린트는 Cloud 런타임 노드 스키마와 맞는 조합을 빠르게 찾는 데 유리하다.
- 로컬 JSON을 바로 제출하기 전에 템플릿/블루프린트 기준으로 노드 입력 키를 교차검증하면 `required_input_missing`류 오류를 줄일 수 있다.
- 제출 후에는 `jobs` 상태 추적과 함께 `execution_error` 페이로드를 저장해 재현 가능한 워크플로 수정 루프를 만든다.

## 3.2) `workflow_api.json` 샘플 (FLUX dual-clip 4-step)
아래 샘플은 `yadam`에서 검증한 캐릭터 1인 시트용 최소 워크플로 구조다.

```json
{
  "5": {
    "class_type": "EmptyLatentImage",
    "inputs": { "width": 960, "height": 1280, "batch_size": 1 }
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "single Korean Joseon male character sheet, one subject, full body, white background, no text",
      "clip": ["11", 0]
    }
  },
  "10": {
    "class_type": "VAELoader",
    "inputs": { "vae_name": "ae.safetensors" }
  },
  "11": {
    "class_type": "DualCLIPLoader",
    "inputs": {
      "clip_name1": "t5xxl_fp16.safetensors",
      "clip_name2": "clip_l.safetensors",
      "type": "flux"
    }
  },
  "12": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "flux1-schnell.safetensors",
      "weight_dtype": "default"
    }
  },
  "16": {
    "class_type": "KSamplerSelect",
    "inputs": { "sampler_name": "euler" }
  },
  "17": {
    "class_type": "BasicScheduler",
    "inputs": {
      "scheduler": "simple",
      "steps": 4,
      "denoise": 1,
      "model": ["12", 0]
    }
  },
  "22": {
    "class_type": "BasicGuider",
    "inputs": {
      "model": ["12", 0],
      "conditioning": ["6", 0]
    }
  },
  "25": {
    "class_type": "RandomNoise",
    "inputs": { "noise_seed": 70781 }
  },
  "13": {
    "class_type": "SamplerCustomAdvanced",
    "inputs": {
      "noise": ["25", 0],
      "guider": ["22", 0],
      "sampler": ["16", 0],
      "sigmas": ["17", 0],
      "latent_image": ["5", 0]
    }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["13", 0],
      "vae": ["10", 0]
    }
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {
      "filename_prefix": "YADAM_FLUX_SCHNELL_CHAR",
      "images": ["8", 0]
    }
  }
}
```

운용 팁:
- 위 JSON은 즉시 제출 가능한 API format이다.
- 동적 치환이 필요하면 `unet_name`, `text`, `noise_seed`, `width/height`를 실행 시점에 바꿔서 제출한다.
- 동일 구조의 placeholder 버전은:
  - `yadam/config/comfy_workflows/yadam_api_flux_schnell_dualclip4_placeholders.json`

## 4) 인증/경로 주의사항
- `https://cloud.comfy.org/`(루트)는 UI 경로가 섞여 실패 원인 분석이 어렵다.
- API 전용 base URL은 `https://cloud.comfy.org/api`를 사용한다.
- Cloud에서는 `history` 대신 `jobs` 경로를 우선 사용한다.
- 인증 헤더는 Cloud 문서 기준 `X-API-Key`를 기본으로 사용한다.

## 5) 모델/워크플로 preflight (필수)
이미지 생성 전 아래 항목을 먼저 확인한다.

1. 모델 존재 확인
```bash
curl -sS -H "X-API-Key: $COMFYUI_API_KEY" \
  "https://cloud.comfy.org/api/experiment/models/checkpoints"
```

2. FLUX dual-clip 조합 확인
- `diffusion_models` 또는 `checkpoints` 중 워크플로와 일치하는 위치의 모델명
- `text_encoders`: `t5xxl_fp16.safetensors`, `clip_l.safetensors`
- `vae`: `ae.safetensors`

3. 워크플로 노드 호환 확인
- Cloud 런타임에서 노드 입력 스키마가 로컬과 다를 수 있음
- 실패 시 `GET /api/jobs/{id}`의 `execution_error`를 기준으로 워크플로 수정

## 6) yadam에서 검증된 실무 패턴

### A. 빠른 1차 생성 (base)
- 워크플로: `yadam_api_flux_schnell_dualclip4_placeholders.json`
- 목적: seed 다건 후보를 빠르게 확보
- 장점: 속도/성공률
- 단점: 텍스트/신발/연령 드리프트 가능

### B. 2차 보정 (img2img refine)
- 워크플로: `yadam_api_flux_schnell_refine_img2img_placeholders.json`
- 목적: 1차 베스트 컷을 reference로 신발/머리/비율 미세 보정
- 권장: 낮은 denoise(예: 0.2~0.4)로 아이덴티티 유지

## 7) 캐릭터 시트 품질 게이트
- 필수 통과:
  - 인물 1명
  - 전신(발 포함)
  - 배경 없음
  - 텍스트/로고/낙관 없음
  - 고증 위반 없음(현대 신발/현대 헤어 금지)
- 권장:
  - seed 4~8장 생성 후 통과 컷 선택
  - 선택 컷으로 refine 1~2회

## 8) 자주 발생한 실패와 대응
- `HTTP_401 Authentication required`:
  - base URL/헤더 확인 (`/api`, `X-API-Key`)
- `authentication method not allowed`:
  - 잘못된 엔드포인트(`history` 등) 사용 가능성
  - `jobs` 경로로 전환
- `ckpt_name not in list`:
  - 모델 파일명/폴더 불일치
  - `/api/experiment/models/{folder}`로 존재 확인
- `required_input_missing`:
  - 노드 버전 차이(Cloud 런타임 스키마 변경)
  - `GET /api/object_info`로 해당 노드의 필수 입력키 확인 후 보정
- `ImageDownloadError`:
  - reference 이미지 토큰이 비어 있거나 업로드 실패
  - consistency 템플릿에서 `__REF_IMAGE_1__` 주입 검증

## 8.1) Job 운영 노하우
- 상태 추적은 `jobs/{id}`를 기준으로 하고, 대량 모니터링은 `jobs/list`를 사용한다.
- 장시간 큐 적체 시 `queue`를 먼저 확인하고, 필요 시 `interrupt`/`queue` 관리 API로 정리한다.
- 디버그에 필요한 최소 저장 항목:
  - `prompt_id`
  - `status`
  - `execution_error.exception_message`
  - 제출한 workflow JSON 해시
- 정기적으로 히스토리를 정리해(`history` 관리 API) 잡 조회 성능을 유지한다.

## 9) 권장 운영 루틴
1. `.comfyui.env` 로드
2. 모델/텍스트인코더/VAE preflight
3. base 워크플로로 seed 다건 생성
4. 품질 게이트 통과 컷 선택
5. img2img refine으로 미세 보정
6. 최종 컷을 `project.json` 메타에 반영

## 10) 자동 실행 스크립트
`scripts/comfy_cloud_charsheet_workflow.py`

### 10.1) base 멀티시드 후보 생성
```bash
set -a; source .comfyui.env; set +a
STORY_ID="storyNN"
CHAR_ID="char_001"
PYTHONPATH=. .venv/bin/python scripts/comfy_cloud_charsheet_workflow.py \
  --story-id "$STORY_ID" \
  --char-id "$CHAR_ID" \
  --mode base \
  --model flux1-schnell.safetensors \
  --seeds 10121,20231,30341,40451,50561,60671,70781,80891
```

### 10.2) refine (선택컷 기준)
```bash
set -a; source .comfyui.env; set +a
STORY_ID="storyNN"
CHAR_ID="char_001"
REF_IMAGE="work/${STORY_ID}/characters/candidates_${CHAR_ID}/${CHAR_ID}_seed70781.jpg"
PYTHONPATH=. .venv/bin/python scripts/comfy_cloud_charsheet_workflow.py \
  --story-id "$STORY_ID" \
  --char-id "$CHAR_ID" \
  --mode refine \
  --model flux1-schnell.safetensors \
  --reference-image "$REF_IMAGE" \
  --seed 917071
```

## 11) Z-Image Turbo 인물 출력 노하우 (실전)

### 11.1) 반드시 맞춰야 하는 모델 조합
- UNET: `z_image_turbo_bf16.safetensors` (`diffusion_models`)
- CLIP: `qwen_3_4b.safetensors` (`text_encoders`)
- VAE: `ae.safetensors` (`vae`)
- CLIPLoader `type`: `lumina2`
- 샘플러: `KSampler + res_multistep + simple`
- 보조 노드: `ModelSamplingAuraFlow`

### 11.2) 검증된 워크플로 파일
- base: `yadam/config/comfy_workflows/yadam_api_z_image_base_placeholders.json`
- turbo: `yadam/config/comfy_workflows/yadam_api_z_image_turbo_placeholders.json`

### 11.3) 실행 예시 (turbo, 임의 story-id/char-id)
```bash
set -a; source .comfyui.env; set +a
STORY_ID="storyNN"
CHAR_ID="char_001"
PYTHONPATH=. .venv/bin/python scripts/comfy_cloud_charsheet_workflow.py \
  --story-id "$STORY_ID" \
  --char-id "$CHAR_ID" \
  --mode base \
  --workflow-path yadam/config/comfy_workflows/yadam_api_z_image_turbo_placeholders.json \
  --model z_image_turbo_bf16.safetensors \
  --seeds 10101,20202
```

### 11.4) 프롬프트 운영 규칙 (텍스트 유입 방지)
- 프롬프트에 캐릭터 이름 한글을 직접 넣지 않는다.
  - 이름 한글을 넣으면 이미지에 글자로 새겨질 확률이 올라간다.
- 문장에 `absolutely no text or symbols anywhere in image`를 포함한다.
- negative에 아래 키워드를 강하게 포함한다.
  - `text, letters, words, typography, title, caption, hangul, hanja, watermark, logo, stamp, signature`
- 복장/헤어 고정이 필요하면 구체적으로 잠근다.
  - 예: `neat sangtu topknot`, `no bangs`, `no short modern haircut`

### 11.5) 자주 겪은 실패와 해결
- `normalized_shape ... got input of size ...`:
  - 원인: FLUX 워크플로에 Z-Image 모델을 끼워 넣은 구조 미스매치
  - 해결: Z-Image 전용 워크플로(`z_image_*_placeholders.json`) 사용
- `authentication method not allowed`:
  - 원인: Cloud에서 일부 엔드포인트/인증 방식 불일치
  - 해결: base URL을 `https://cloud.comfy.org/api`로 고정하고 `X-API-Key` 사용
- SSL handshake/network timeout:
  - 원인: Cloud 일시 장애/네트워크 변동
  - 해결: 실패 캐릭터만 seed 고정 재시도(전체 재생성 금지)

### 11.6) 범용 품질 게이트 (모든 story 공통)
- 통과 조건:
  - 인물 1명, 전신, 무배경, 무텍스트
  - 조선 복장/헤어 고증 유지
  - 현대 신발/레이스업/로고 금지
- 실전 팁:
  - 후보 2~3 seed 후 즉시 육안 검수
  - 인페인트로 신발만 고치려다 스타일이 깨지면, turbo 재샘플이 더 안정적
  - 캐릭터별로 `기준 스타일 이미지 1장`을 먼저 확정한 뒤, 나머지 캐릭터를 같은 규칙으로 확장하면 일관성이 좋아진다.

## 12) Z-Image Turbo 장소(place) 출력 노하우 (범용)

### 12.1) 기본 원칙
- place도 `Z-Image Turbo`를 기본 모델로 사용한다.
- 목표 톤은 실사가 아니라 다음 계열로 고정한다.
  - `Korean historical illustration style`
  - `semi-realistic cinematic matte painting`
  - `painterly brush texture`

### 12.2) 하드 네거티브 규칙
- 텍스트/간판/워터마크: `text, letters, words, typography, signboard, watermark`
- 현대물: `electric wires, utility pole, power line, street lamp, traffic sign, car, asphalt road`
- 실사 드리프트: `photorealistic photo, camera lens realism`

### 12.3) 빠른 실행 스크립트
새 범용 스크립트:
- `scripts/comfy_cloud_place_refs_workflow.py`

예시:
```bash
set -a; source .comfyui.env; set +a
PYTHONPATH=. .venv/bin/python scripts/comfy_cloud_place_refs_workflow.py \
  --story-id storyNN
```

특정 place만 재생성:
```bash
set -a; source .comfyui.env; set +a
PYTHONPATH=. .venv/bin/python scripts/comfy_cloud_place_refs_workflow.py \
  --story-id storyNN \
  --place-ids place_001,place_003
```

### 12.4) 검수 포인트
- 조선 시대 place에서 전봇대/전선이 보이면 즉시 재생성한다.
- `used_by_scenes`가 많은 place부터 우선 점검한다.
- 스타일이 실사로 치우치면 prompt에 non-photoreal anchor를 추가하고 동일 place만 다시 생성한다.
