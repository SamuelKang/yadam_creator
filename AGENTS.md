# AGENT HANDOFF / SESSION ROLE

이 문서는 다음 세션에서 에이전트가 **가장 먼저 읽고** 동일한 작업 방식을 유지하기 위한 운영 규칙이다.

## 1) 역할 정의
- 이 저장소의 에이전트는 `yadam` 파이프라인의 실무 유지보수 엔지니어 역할을 수행한다.
- 목표는 다음을 안정적으로 자동화/개선하는 것이다.
  - `title -> synopsis -> story -> images -> .vrew`
  - 한국어 대사 자연성, 장면 분할 안정성, 인물 일관성, Vrew 호환성
- 답변은 간결하고 사실 중심으로 작성한다.

## 2) 작업 우선순위
1. 실행 실패 원인 파악(로그/`project.json` 기준)
2. 재실행 가능 상태 복구(`pending` 초기화, 실패 산출물 정리)
3. 재발 방지 코드 수정(규칙/파서/재시도/태깅)
4. 검증(`py_compile` 또는 최소 재현)
5. 문서화(`docs/changes.md`)와 커밋/푸시(요청 시)

## 3) 필수 운영 원칙
- 런타임 산출물(`work/...`, `stories/...`)과 코드 변경을 구분한다.
  - 런타임 보정은 문제 해결용 상태 조정으로 수행
  - 코드/프롬프트 변경만 커밋 대상으로 본다(사용자 요청 시 예외)
- 사용자가 명시하지 않은 파괴적 명령(`reset --hard` 등)은 금지.
- 새 규칙을 넣을 때는 가능하면 **조건부 규칙**으로 넣어 토큰/부작용을 줄인다.
- 새 세션 시작 시, 전역 스킬 목록만 믿지 말고 이 저장소의 로컬 스킬 존재를 직접 확인한다.
  - 우선 확인 대상: `skills/make_vrew/SKILL.md`
  - 구조/룰만 다루는 작업이면 `skills/yadam-structure-rules/SKILL.md`도 함께 확인한다.
  - 사용자가 `story-id` 기반 이미지/clip/`.vrew` 작업을 요청하면, 가능하면 먼저 `make_vrew` 로컬 스킬 기준으로 진행한다.

## 4) 이 프로젝트에서 특히 지킬 사항
- `llm_scene_prompt.py`:
  - shot-first, 짧은 영어 scene prompt 지향
  - 직접 대사/인용부호 금지(행동 묘사로 대체)
  - 조선 고증 규칙 유지(실내 서양식 fireplace 금지, 한국형 `ㄱ`자 낫 같은 생활 소도구 실루엣 유지 등)
  - clip image용 `llm_clip_prompt`의 최종 작성 책임은 Codex에 있다.
  - LLM extract 결과는 초안으로만 취급하고, 비어 있거나 품질 미달이면 Codex가 `project.json`에서 직접 생성/보정 후 다음 단계로 진행한다.
- 인물 일관성:
  - 실명 canonical + 역할명 alias
  - 성장 서사는 분리 캐릭터 대신 variants 우선
  - scene `characters/character_instances` 누락 최소화
  - 아동 주인공 drift가 보이면 prompt에 체형/연령/머리장식/도포 색을 다시 명시한다.
  - 같은 장면에 주인공 중복 생성이 나왔으면 `exactly one boy/one guard/...`처럼 인원 수를 직접 잠근다.
  - 후반부 화상, 관복, 규수 복장처럼 상태 전환이 끝난 구간은 `stories/<story-id>_variant_overrides.yaml`와 `stories/<story-id>_scene_bindings.yaml`에도 같이 남긴다.
- Gemini 이미지:
  - `image_config.aspect_ratio` 명시
  - `reference_image_paths`(핵심 1~2명) 활용
  - `EMPTY_IMAGE_BYTES`는 프롬프트 민감도 완화 후 scene 단위 재시도
  - `EMPTY_IMAGE_BYTES`가 특정 scene에서 반복되면 인물 수/행동/배경을 줄인 짧은 prompt로 바꾸고 해당 scene만 `pending` 재생성한다.
  - 액션 의미가 중요한 장면은 “무릎 꿇음” 같은 표면 포즈보다 대본의 실제 행위(예: 단서 줍기, 몸을 굽혀 살피기)를 우선 반영한다.

## 5) CLI 동작 기대치
- 기본 `--story-id`:
  1) synopsis 생성/확인
  2) story 생성/확인
  3) 이미지 + `.vrew` 진행
- `--non-interactive`:
  - 확인 없이 전 단계 자동 진행
  - 단, hash 기반으로 불필요 재생성은 건너뛴다.
- `--title`:
  - 새 `storyNN.title`에서 시작하는 end-to-end 경로

## 6) 에러 대응 표준
- `429 RESOURCE_EXHAUSTED`: quota/rate limit. 프롬프트 수정보다 재시도 타이밍/경로 점검 우선.
- `500 INTERNAL`: transient. 백오프 재시도 우선.
- `EMPTY_IMAGE_BYTES`: 장면 민감도 완화 + 해당 scene만 `pending` 재생성.
- 말풍선/텍스트 유입: scene prompt에서 직접 발화문 제거 규칙 점검.

## 7) 세션 종료 전 체크리스트
- 변경 파일 문법 검증 완료
- 사용자 요청 범위 외 파일 revert 없음
- 필요한 경우 `changes.md` 업데이트
- 커밋/푸시 요청이 있으면 수행, 없으면 작업트리 상태 보고

## 8) 커밋/푸시 기본 규칙
- 사용자가 커밋을 요청한 경우, 특별히 중단 지시가 없는 한 **커밋 직후 같은 턴에서 push까지 연속 수행**한다.
- push 대상은 기본적으로 `origin/main`이며, 실패 시 원인(권한/네트워크/충돌)을 즉시 보고하고 다음 조치를 제안한다.
- 런타임 산출물(`stories/`, `work/`)은 사용자가 명시적으로 원하지 않는 한 커밋/푸시 대상에서 제외한다.

## 9) 로컬 Comfy Cloud 키 위치
- Comfy Cloud API 키는 저장소 루트의 `.comfyui.env`에 저장되어 있다.
- 다음 세션에서 Comfy Cloud 작업을 시작할 때 먼저 이 파일을 로드한다.
  - 예: `set -a; source .comfyui.env; set +a`
- `.comfyui.env`는 로컬 비밀 파일이며 git commit/push 대상에서 제외한다.

## 10) Z-Image Turbo 운영 메모 위치
- Comfy Cloud + Z-Image Turbo 인물 출력 노하우는 `docs/comfy_cloud_playbook.md`의 `11) Z-Image Turbo 인물 출력 노하우 (실전)` 섹션을 기준으로 따른다.
- 다음 세션에서 어떤 `story-id` 작업을 재개하더라도 위 섹션의 모델 조합/프롬프트 규칙/실패 대응을 먼저 확인한다.
