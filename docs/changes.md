변경 이력 (Change Log)

본 문서는 docs/requirements.md(요구사항)과 구현/운영 규격의 변경 사항을 누적 기록한다.
각 항목은 “무엇이/왜/어떻게 바뀌었는지”를 최소 단위로 남긴다.

⸻

작성 규칙
	•	날짜는 KST 기준 YYYY-MM-DD
	•	한 변경은 1개 항목으로 기록
	•	가능하면 영향 범위를 명시한다(모듈/디렉토리/스키마/CLI 등)
	•	구현이 동반되면 관련 커밋/브랜치를 함께 적는다(선택)

⸻

템플릿

[YYYY-MM-DD] 변경 제목
	•	구분: (요구사항/설계/구현/운영)
	•	변경 내용:
	•	(무엇이 바뀌었는지)
	•	변경 이유:
	•	(왜 바꿨는지)
	•	영향 범위:
	•	(예: CLI, JSON 스키마, 디렉토리 구조, 이미지 생성, 리라이트 룰 등)
	•	마이그레이션/호환:
	•	(기존 데이터/폴더/파일을 어떻게 처리할지)
	•	비고:
	•	(추가 메모)

⸻

변경 이력

[2026-03-15] make_vrew clip prompt 규칙에 standalone 이미지 프롬프트와 guard 연기 지침 추가

- 목적
	- 다른 story에서도 clip prompt가 고유명사나 이전 장면 문맥에 기대어 drift되거나, 경호 인물이 정면 정자세로 굳는 문제를 줄이기 위함.
- 변경
	- `skills/make_vrew/SKILL.md`의 step-9 prompt review 기준에 다음을 명시:
	- 고유명사/scene-number reference에 기대지 않는 standalone prompt 작성
	- 역할/나이/복장/시각 앵커 중심의 인물 서술
	- `grim resolve` 같은 추상 감정어 대신 drawable acting cue 사용
	- guard/bodyguard 캐릭터에 scan, shield, lean, crouch, half-draw 같은 구체 동작 부여
	- `skills/make_vrew/references/clip_prompt_review.md`, `skills/make_vrew/references/clip_prompt_repair.md`에 같은 기준과 예시를 추가.
- 영향
	- 이후 `make_vrew` 기반 story의 clip prompt 수리/재생성 세션 전반.

[2026-03-13] through-tag-scene/재개 경로에서 기존 synopsis/story 우선 재사용

- 목적
	- `story-id` 기반 재개 작업에서 `stories/<story-id>.synopsis`, `stories/<story-id>.txt`가 이미 있어도 hidden hash 부재 때문에 synopsis/story 재생성이 다시 걸리는 문제를 막기 위함.
- 변경
	- `yadam/cli.py`에서 `--through-tag-scene`, `--through-place-refs`, `--through-clips` 경로일 때는 기존 synopsis/story 파일이 있으면 hidden hash 파일이 없어도 우선 재사용하도록 조정.
	- 재사용 시 missing hash 파일은 현재 입력 기준으로 보강 저장.
- 영향
	- `make_vrew` 같은 재개/부분 실행 워크플로우에서 불필요한 LLM 호출 감소.

[2026-03-13] scene prompt 연속 반복 억제와 story26 continuity 규칙 보강

- 목적
	- 인접 장면이 같은 배경·같은 포즈로 반복되거나, 인질 표정/가마/낫 같은 조선 고증과 행동 상태가 자주 흔들리는 문제를 줄이기 위함.
- 변경
	- `yadam/nlp/llm_scene_prompt.py`에 인접 scene shot 변주, 동일 장소 배경 앵커 유지, 인질 표정 제한, 한국형 낫, 무륜 조선 가마 규칙을 조건부로 추가.
	- `stories/story26_scene_bindings.yaml`, `stories/story26_variant_overrides.yaml`에 `story26` 전용 continuity 잠금 규칙을 추가.
- 영향
	- `story26` 재생성 구간과 이후 유사한 조선 산길/움막/인질/가마 장면의 clip prompt 안정성 개선.

[2026-03-13] clip 육안 검수 노하우와 중복 인물/실루엣 자객/가마 오판 방지 규칙 보강

- 목적
	- 자동 검사만으로는 놓치는 반복 포즈, 그림자형 적, 동일 인물 복제, 아동 연령/복장 드리프트, 가마 탑승자-운반자 혼선 문제를 줄이기 위함.
- 변경
	- `yadam/nlp/llm_scene_prompt.py`에 centered standing 반복 억제, 무표정 고정 방지, duplicate figure 금지, 팔/손 좌우 융합 방지, silhouette-only 자객 금지, 가마 승객/운반자 분리, 16:9 비율 왜곡 방지 규칙을 추가.
	- `skills/make_vrew/SKILL.md`, `skills/make_vrew/references/clip_image_review.md`, `skills/make_vrew/references/clip_prompt_repair.md`에 contact sheet 기반 육안 검수와 위 실패 유형별 수리 지침을 추가.
- 영향
	- `make_vrew` 운영 세션에서 사용자 피드백 기반 clip 재수리 속도와 재발 방지 정확도가 개선.

[2026-03-13] 조선 생활 소도구 고증에 한국형 ㄱ자 낫 예시 추가

- 목적
	- 약초꾼/농기구 캐릭터 reference에서 서양식 scythe형 낫이 섞이는 문제를 줄이기 위함.
- 변경
	- `skills/make_vrew/references/character_ref_review.md`에 조선 생활 소도구 실루엣 검수 항목 추가.
	- `docs/requirements.md`, `AGENTS.md`에 한국형 `ㄱ`자 낫을 조선 고증 예시로 명시.
- 영향
	- 이후 character reference review와 조선 고증 판단에서 낫 형태도 하드 체크 항목으로 취급.

[2026-03-13] .vrew 자막 2줄 우선 분할 및 export 후 caption 검수 추가

- 목적
	- `.vrew` 결과에서 한 caption이 3줄 이상으로 자주 보이는 문제를 줄이고, 화면 가독성과 TTS 호흡 단위를 함께 맞추기 위함.
- 변경
	- `yadam/export/vrew_exporter.py`에서 caption을 기본 2줄 이하로 맞추는 방향으로 chunk 재분할과 줄바꿈 휴리스틱을 강화.
	- 문장 길이가 길어 2줄을 넘기기 쉬운 경우, export 단계에서 의미 단위 기준으로 clip을 추가 분할하도록 보강.
	- `skills/make_vrew/scripts/check_vrew_captions.py` 추가.
	- `skills/make_vrew/SKILL.md`에 export 후 caption line-count 검수 절차 추가.
- 사용
	- `python skills/make_vrew/scripts/check_vrew_captions.py --story-id story14`

[2026-03-11] continuity 검수용 contact sheet 추가

- 목적
	- Codex 세션에서 고해상도 clip 여러 장을 연속으로 `Viewed Image` 하면 응답 payload가 커져 `413 Payload Too Large`가 날 수 있어, continuity 검수 전용 축소본 1장으로 대체하기 위함.
- 변경
	- `scripts/make_contact_sheet.py` 추가.
	- `work/<story-id>/clips/*.jpg` 여러 장을 읽어 `work/<story-id>/out/<story-id>_clips_<start>_<end>_sheet.jpg` 한 장으로 저장.
	- 각 장면에 번호 라벨을 붙이고, 기본 썸네일 폭과 JPEG 품질을 낮춰 세션 검수용 페이로드를 줄임.
- 사용
	- `python3 scripts/make_contact_sheet.py --story-id story25 --scenes 112-118`

[2026-02-23] story_id 기반 입력/출력 디렉토리 규칙 확정
	•	구분: 요구사항/설계
	•	변경 내용:
	•	입력은 story_id(예: story00)로 받고, 대본은 stories/{story_id}.txt에서 읽는다.
	•	결과물은 work/{story_id}/ 아래에 스토리별로 정리한다.
	•	stories/와 work/ 디렉토리는 없으면 자동 생성한다.
	•	변경 이유:
	•	재실행/재시도/비교(스토리 단위 관리) 및 운영 편의성 향상.
	•	영향 범위:
	•	CLI 인자(--story-id), 경로 계산, 출력 폴더 구조
	•	마이그레이션/호환:
	•	기존 방식 사용 시, 새 규칙으로 래핑하거나 CLI 옵션 유지 필요(선택).
	•	비고:
	•	--create-empty-story 옵션으로 입력 파일이 없을 때 빈 파일 생성 가능.

[2026-02-23] 이미지 생성 실패 시 error 파일 및 JSON 상태 유지 규칙 확정
	•	구분: 요구사항/설계
	•	변경 내용:
	•	장면 이미지 생성 실패 시 clips/006_error.jpg 같은 파일을 남기고 파이프라인은 중단하지 않는다.
	•	재시도 성공 시 _error 파일은 삭제하고 성공 파일로 대치한다.
	•	JSON에는 status/attempts/last_error/path/prompt_history 등을 기록한다.
	•	변경 이유:
	•	API 오류/정책 차단이 있어도 전체 산출물을 확보하고, 재개(Resume) 가능하게 하기 위함.
	•	영향 범위:
	•	이미지 생성 모듈, JSON 스키마, 재시도/재개 로직
	•	마이그레이션/호환:
	•	기존 산출물에 상태 필드가 없다면 최초 실행 시 기본값으로 보강 필요.
	•	비고:
	•	tmp 저장 후 rename(원자적 교체) 사용 권장.

[2026-02-23] 정책 차단 시 프롬프트 자동 리라이트 후 재시도 규칙 확정
	•	구분: 요구사항/설계
	•	변경 내용:
	•	정책(안전 필터) 차단으로 판단되면 프롬프트를 레벨(1~3)로 완화하여 재시도한다.
	•	실패 확정 시 _error 유지 + JSON에 policy_rewrite_level 및 이력 기록.
	•	변경 이유:
	•	동일 장면이 반복 차단되는 것을 자동으로 완화해 처리하기 위함.
	•	영향 범위:
	•	에러 분류 로직, 프롬프트 리라이터, 재시도 정책
	•	마이그레이션/호환:
	•	기존 prompt 기록이 없다면 prompt_history는 빈 배열로 시작.

[2026-02-23] 시대/화풍 프로필(era/style) 분리 설계 확정
	•	구분: 요구사항/설계
	•	변경 내용:
	•	조선 야담/현대 시니어 사연 등 시대 프리셋(era)과 화풍 프리셋(style)을 분리한다.
	•	JSON에 era_profile, style_profile을 기록하고, 프롬프트는 “콘텐츠 레이어 + 스타일 레이어”로 합성한다.
	•	변경 이유:
	•	동일 대본/장면에 대해 화풍만 바꿔 재생성 가능한 구조 확보.
	•	영향 범위:
	•	설정 파일(default_profiles.yaml), 프롬프트 빌더, JSON project 메타
	•	마이그레이션/호환:
	•	프로젝트에 era/style이 없다면 기본값을 설정한다.

[2026-02-24] LLM 기반 인물/장소 정규화 및 장면 태깅 도입
	•	구분: 설계/구현
	•	변경 내용:
	•	규칙 기반 후보(seed) + LLM 정규화를 결합하여 characters/places/scene_tags를 생성.
	•	LLM이 visual_anchors를 생성하고, 캐릭터/장소 프롬프트에 우선 반영.
	•	변경 이유:
	•	호칭/별칭/대명사 처리 및 캐릭터/장소 일관성 향상.
	•	영향 범위:
	•	yadam/nlp/llm_extract.py, orchestrator.py, builder.py, project.json 스키마

[2026-02-24] 이미지 생성 프롬프트 디버깅 정보(project.json) 강화
	•	구분: 구현/운영
	•	변경 내용:
	•	이미지 생성 메타에 prompt_original, prompt_used, prompt_history 기록.
	•	변경 이유:
	•	정책 차단/품질 문제 원인 추적 목적.
	•	영향 범위:
	•	yadam/gen/image_tasks.py, project.json 스키마

[2026-02-24] clip 텍스트 억제 강화 및 clip 전용 스타일 도입
	•	구분: 설계/구현
	•	변경 내용:
	•	clip 프롬프트에 말풍선/자막/캡션/패널/내레이션 박스/텍스트 박스 금지 문구 강화.
	•	style_profiles.k_webtoon_clip을 clip 전용으로 사용 가능.
	•	변경 이유:
	•	웹툰 스타일에서 문자 포함 확률이 높아 clip 품질/편집성 저하.
	•	영향 범위:
	•	builder.py, default_profiles.yaml, orchestrator.py

[2026-02-24] Vertex 모드와 Developer(API Key) 모드 혼용 문제 정리
	•	구분: 운영/구현
	•	변경 내용:
	•	키/환경변수 혼용 시 라우팅 혼선 가능 → 분리 운용 권장.
	•	Developer 모드에서 일부 이미지 생성 파라미터 미지원 확인 → 모드별 분기 필요.
	•	변경 이유:
	•	실행 시 라우팅 혼선 및 기능 차이로 인한 실패 방지.
	•	영향 범위:
	•	환경 구성, 이미지 생성 클라이언트 설정, 운영 절차

[2026-02-24] LLM 호출에서 system role 미지원 이슈 대응
	•	구분: 구현
	•	변경 내용:
	•	system role 미지원 오류 발생 → system 지침을 user 메시지에 병합하는 방식으로 변경.
	•	변경 이유:
	•	모델/엔드포인트에 따라 system role이 거부될 수 있어 안정성 확보 목적.
	•	영향 범위:
	•	yadam/nlp/llm_extract.py

⸻

(신규 추가) 2026-02-26 변경분

[2026-02-26] 캐릭터 생성에서 16:9 문구 제거를 위한 캐릭터 전용 스타일 분리
	•	구분: 설계/구현
	•	변경 내용:
	•	캐릭터 이미지 생성(3:4)에서 기본 스타일(k_webtoon) suffix의 16:9 지시가 섞이는 문제를 해결하기 위해,
	•	캐릭터 전용 스타일 프로필(예: k_webtoon_char)을 도입하고, 캐릭터 생성은 이를 사용하도록 변경.
	•	변경 이유:
	•	캐릭터는 3:4인데 프롬프트에 16:9가 들어가 결과 품질/지시 일관성이 깨지는 문제 방지.
	•	영향 범위:
	•	default_profiles.yaml(style_profiles), orchestrator.py(캐릭터 프롬프트 생성)
	•	마이그레이션/호환:
	•	기존 프로젝트 재생성 시 캐릭터 프롬프트가 변경되므로, 필요하면 캐릭터 이미지를 재생성(삭제 후 생성)한다.

[2026-02-26] LLM 호출 지연 구간에 heartbeat 출력 추가
	•	구분: 구현/운영
	•	변경 내용:
	•	LLM 호출이 긴 구간(예: entity extract)에서 진행상황이 보이도록 . 출력(주기 1초) 및 60초마다 줄바꿈 로그 출력.
	•	변경 이유:
	•	“[2/7] LLM extract: start” 이후 멈춘 것처럼 보이는 문제 해결.
	•	영향 범위:
	•	orchestrator.py(heartbeat wrapper)

[2026-02-26] 아동 연령 기준을 5세로 고정
	•	구분: 요구사항/구현
	•	변경 내용:
	•	“아동”은 기본적으로 “약 5세”를 프롬프트/LLM 입력에 반영한다.
	•	단, 기존 age_hint가 있으면 이를 우선한다.
	•	변경 이유:
	•	이미지 생성 시 아동의 연령대가 흔들려 캐릭터 일관성이 깨지는 문제 방지.
	•	영향 범위:
	•	캐릭터 프롬프트 빌드, clip LLM scene prompt 입력 데이터 구성

[2026-02-26] 폴더 자동 열기 동작 비활성화
	•	구분: 운영/구현
	•	변경 내용:
	•	실행 과정에서 Finder로 work/characters 등 폴더가 연속으로 열리는 동작을 전면 비활성화(코멘트 처리).
	•	변경 이유:
	•	작업 흐름 방해(창 다중 오픈) 문제 해결.
	•	영향 범위:
	•	orchestrator.py(폴더 오픈 호출부)

[2026-02-26] CLI --clean-workdir 삭제 절차 및 --non-interactive 결합 규칙 확정
	•	구분: 요구사항/구현
	•	변경 내용:
	•	--clean-workdir는 work/{story_id}만 삭제 대상으로 제한(경로 탈출 방지).
	•	삭제 확인은 반드시 y 또는 n만 허용(엔터 무효).
	•	--non-interactive와 함께 쓰면 --clean-workdir 확인을 먼저 받고, 그 이후 비대화형으로 진행.
	•	변경 이유:
	•	“삭제 여부 확인이 중복되거나”, “비대화형인데 삭제 확인이 생략되는” 혼선 방지.
	•	영향 범위:
	•	yadam/cli.py(옵션 처리, 확인 로직)

[2026-02-26] clips 진행 로그에 누적 경과시간(elapsed) 표기 추가
	•	구분: 구현/운영
	•	변경 내용:
	•	[6/7] clips 진행 로그에 elapsed~{time} 필드를 추가해, 현재까지 누적 경과 시간을 ETA와 함께 출력.
	•	변경 이유:
	•	ETA가 “남은 시간”만 보여주어 실제로 얼마나 진행됐는지 즉시 파악하기 어려운 문제 개선.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py(clips 진행 로그 출력부)
	•	마이그레이션/호환:
	•	없음(로그 출력 형식만 변경).

[2026-02-26] clip LLM 프롬프트에 시대 배경 지시(era prefix) 직접 전달
	•	구분: 요구사항/구현
	•	변경 내용:
	•	clip 장면 프롬프트 생성 시 era_profile 이름만 전달하던 방식에서, era prefix(예: “배경: 조선시대. 의복과 소품은 조선시대 양식...”)를 함께 전달하도록 변경.
	•	LLM 규칙에 “시대지시가 제공되면 반드시 반영” 조건을 추가.
	•	변경 이유:
	•	“조선시대 배경” 같은 시대 맥락이 프롬프트에 약하게 반영되는 문제를 방지하고 시대 고증 일관성을 높이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py(입력 스키마/규칙), yadam/pipeline/orchestrator.py(호출 파라미터)
	•	마이그레이션/호환:
	•	없음(기존 데이터 스키마 변경 없음).

[2026-02-26] 이미지 생성 백엔드 선택 구조 도입(Vertex Imagen / Gemini Flash Image)
	•	구분: 요구사항/구현
	•	변경 내용:
	•	CLI에 --image-api 옵션을 추가해 vertex_imagen 또는 gemini_flash_image를 선택 가능하게 변경.
	•	CLI에 --image-model 옵션을 추가해 API별 기본 모델 대신 사용자 지정 모델을 주입할 수 있게 변경.
	•	Gemini Flash Image용 ImageClient 구현(GeminiFlashImageClient) 추가.

[2026-02-27] 챕터 마커(§§CHAPTER|...§§)가 scene 텍스트에 누수되는 문제 수정
	•	구분: 구현
	•	변경 내용:
	•	`attach_chapters()`에서 문장 앞에 붙은 챕터 마커를 반복적으로 분리/인식한 뒤 본문만 남기도록 처리.
	•	기존 “문장 전체가 마커일 때만 인식”하던 한계를 보완.
	•	변경 이유:
	•	문장 분리기가 줄바꿈 경계를 보존하지 못하는 경우, 첫 clip 자막에 `CHAPTER` 문자열이 노출되는 문제 해결.
	•	영향 범위:
	•	yadam/nlp/chapter_split.py
	•	마이그레이션/호환:
	•	기존 산출물(project.json/.vrew)에는 이미 누수된 텍스트가 남아 있을 수 있어 재생성이 필요할 수 있음.

[2026-02-27] .vrew export 워터마크 강제 삽입 제거
	•	구분: 구현
	•	변경 내용:
	•	Vrew exporter에서 워터마크 리소스 상수/파일 등록/`props.waterMark` 메타를 모두 제거.
	•	zip 작성 시 `media/vrewmark_white_01.png`를 더 이상 포함하지 않음.
	•	변경 이유:
	•	결과물 첫 clip 및 전체 프로젝트에 불필요한 워터마크가 자동 노출되는 동작 제거.

[2026-03-02] .vrew 화면/TTS 텍스트 정규화 및 인용문 clip 분할 보정
	•	구분: 구현
	•	변경 내용:
	•	Vrew exporter에서 TTS 텍스트 정규화 시 괄호 보충 설명(예: `천기(天機)`)을 제거하도록 변경.
	•	화면용 clip 분할에서 닫는 따옴표 뒤 조사(`는` 등)를 앞 인용문과 붙이고, `45자`를 넘는 일부 대사도 더 길게 유지하도록 조정.
	•	`§§CHAPTER|...§§` 마커, 잘못 밀린 따옴표, stray quote로 인해 깨지는 화면 텍스트를 exporter 단계에서 한 번 더 정규화.
	•	변경 이유:
	•	Vrew 음성 읽기 품질과 자막 clip 자연스러움을 높이고, scene 텍스트에 남은 따옴표/챕터 마커 이상이 .vrew에서 그대로 노출되는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 `.vrew`에는 반영되지 않으므로 재export가 필요함.

[2026-03-02] scene.text 생성을 위한 quote-aware 문장 분리 도입
	•	구분: 구현
	•	변경 내용:
	•	`split_sentences_korean()`를 대사 블록 인식 방식으로 재작성해, `"`로 시작한 대사는 닫는 `"`가 나올 때까지 하나의 sentence block으로 유지.
	•	대사 내부 줄바꿈을 보존하고, `다/요` 종결과 `.?!` 종결을 분리 처리해 기존의 이중 분리(`했습니다` / `.`)를 제거.
	•	변경 이유:
	•	project.json의 `scene.text`/`sentences`가 대사 중간에서 끊기거나 닫는 따옴표와 `헤헤.` 같은 꼬리 문장이 다음 scene으로 밀리는 문제를 upstream에서 해결하기 위함.
	•	영향 범위:
	•	yadam/nlp/sentence_split.py, scene 생성 단계 전반
	•	마이그레이션/호환:
	•	기존 project.json에는 자동 반영되지 않으므로 scene 재생성 또는 수동 보정이 필요함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 .vrew 파일은 변경되지 않으며, 변경 반영은 재-export한 신규 파일부터 적용됨.
	•	변경 이유:
	•	속도/품질 비교 테스트를 위해 이미지 생성 API를 실행 시점에 전환할 수 있어야 하기 때문.
	•	영향 범위:
	•	yadam/cli.py, yadam/gen/gemini_client.py, 운영 실행 커맨드
	•	마이그레이션/호환:
	•	기본값은 기존과 동일하게 vertex_imagen + imagen-4.0-generate-001을 사용하므로 기존 실행과 호환.

[2026-02-26] clip LLM 입력에 wealth_level 전달
	•	구분: 구현
	•	변경 내용:
	•	clip 장면 프롬프트 생성용 인물 입력(char_objs)에 wealth_level 필드를 추가.
	•	변경 이유:
	•	복식/분위기 디테일에서 재산 수준 신호를 활용해 장면 일관성을 높이기 위함.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py(_build_llm_scene_prompt)

[2026-02-26] Gemini Developer API 호환을 위한 scene prompt schema 수정
	•	구분: 구현
	•	변경 내용:
	•	scene prompt structured output의 summary 타입을 Dict[str,str]에서 명시 필드 모델(shot/focus/time/place)로 변경.
	•	변경 이유:
	•	Gemini API에서 additionalProperties 미지원 오류(LLM_SCENE_PROMPT_ERROR) 방지.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py
	•	마이그레이션/호환:
	•	없음(응답 의미 동일, 스키마 표현만 변경).

[2026-02-26] 아동 variant 일관성 강화(앵커 필터 + 5세 정규화)
	•	구분: 요구사항/구현
	•	변경 내용:
	•	variant/age_stage가 아동일 때 age_hint를 “약 5세”로 정규화.
	•	아동 장면에서 visual_anchors/wardrobe_anchors의 청년·성인 단서를 필터링.
	•	캐릭터 생성과 clip LLM 입력/continuity lock에 동일 규칙 적용.
	•	변경 이유:
	•	“아동 연화” 장면에서 성인 단서가 섞여 외형/복식이 흔들리는 문제 해결.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py(캐릭터 프롬프트 생성, clip 프롬프트 생성)

[2026-02-26] .vrew 직접 생성 요구사항/기획 확정
	•	구분: 요구사항/기획
	•	변경 내용:
	•	모든 clip 생성 완료 후 project.json과 clips 이미지를 소스로 .vrew 파일을 직접 생성하도록 목표를 확정.
	•	scene별 텍스트는 project.json의 scene.text를 그대로 사용.
	•	scene별 voice는 Vrew 내에서 나중에 교체할 dummy voice를 지정.
	•	scene duration은 .vrew 생성 시 자동 확정하지 않고, Vrew 편집 단계에서 수동 조정.
	•	변경 이유:
	•	후속 편집 워크플로우를 Vrew 중심으로 단순화하고, 스크립트-이미지 매핑을 자동화하기 위함.
	•	영향 범위:
	•	요구사항 문서, export 단계 설계(.vrew builder 신규 구현 예정)
	•	마이그레이션/호환:
	•	초기 단계는 설계 확정이며, 구현 이후 .vrew 생성 옵션/동작이 추가될 예정.

[2026-02-26] .vrew 직접 생성 구현(Zip + project.json + media 이미지)
	•	구분: 구현
	•	변경 내용:
	•	VrewFileExporter를 추가해 project.json/scenes/clips 기준으로 .vrew 파일을 직접 생성.
	•	zip 내부에 media/*.jpeg와 project.json을 기록하고, Vrew 워터마크 리소스를 포함.
	•	scene.text를 자막으로 그대로 반영하고, speaker는 dummy voice("unknown") 메타로 기록.
	•	clip 이미지 상태(status=ok) 및 파일 존재 검증 실패 시 export 에러 처리.
	•	변경 이유:
	•	최종 편집 워크플로우를 Vrew 중심으로 단순화하고, 장면-이미지-텍스트 자동 매핑을 제공하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py, yadam/cli.py(기본 exporter 변경)
	•	마이그레이션/호환:
	•	기존 vrew_payload.json 출력도 유지(디버깅/호환용).

[2026-02-26] .vrew clip 자막 분할(기본 30자) 및 동일 이미지 재사용
	•	구분: 요구사항/구현
	•	변경 내용:
	•	scene.text를 의미 단락(문장 경계 우선) 기준으로 분할해 .vrew clip을 생성하도록 변경.
	•	기본 분할 길이는 30자이며, CLI 옵션 --vrew-clip-max-chars로 조정 가능.
	•	한 scene에서 분할된 하위 clip들은 동일한 scene 이미지를 공통 asset으로 사용.
	•	변경 이유:
	•	Vrew 편집 시 자막/호흡 단위를 더 세밀하게 조정하고, 이미지 일관성을 유지하기 위함.
	•	영향 범위:
	•	yadam/cli.py, yadam/pipeline/orchestrator.py, yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	옵션 미지정 시 기존과 동일하게 자동 export되며, clip 단위만 더 세분화될 수 있음.

[2026-02-27] CLI --help 예시 섹션에 선호 기본 실행 커맨드 추가
	•	구분: 운영/구현
	•	변경 내용:
	•	`python -m yadam.cli --help`의 예시 섹션 최상단에 선호 기본 실행 4개 커맨드를 고정 배치.
	•	향후 업데이트를 고려해 예시 섹션을 별도 블록(epilog)으로 구성.
	•	변경 이유:
	•	반복 사용하는 실행 패턴을 즉시 확인할 수 있게 해 운영 편의성을 높이기 위함.
	•	영향 범위:
	•	yadam/cli.py(argparse description/epilog)

[2026-02-27] CLI 인자 오류 메시지에 간단 실행 예시 출력 및 help 실행 안정화
	•	구분: 운영/구현
	•	변경 내용:
	•	필수 인자 누락 등 argparse 오류 발생 시, 에러 하단에 `--story-id` 포함 간단 실행 예시를 출력하도록 변경.
	•	`--help`만 확인할 때 외부 의존성 미설치로 실패하지 않도록, 무거운 모듈 import를 main() 내부 지연 import로 전환.
	•	변경 이유:
	•	초기 실행 시 사용자 가이드를 즉시 제공하고, 테스트 환경에서 help 확인 가능성을 높이기 위함.
	•	영향 범위:
	•	yadam/cli.py(FriendlyArgumentParser, 지연 import)

[2026-02-27] ComfyUI 이미지 생성 백엔드 추가
	•	구분: 요구사항/구현
	•	변경 내용:
	•	이미지 API 선택지에 `comfyui`를 추가하고, 로컬 ComfyUI 서버를 통해 이미지를 생성할 수 있도록 `ComfyUIImageClient`를 구현.
	•	CLI 옵션 `--comfy-url`, `--comfy-workflow`, `--comfy-timeout-sec`를 추가.
	•	`--comfy-workflow` 미지정 시 `COMFYUI_WORKFLOW_PATH` 환경변수를 fallback으로 사용.
	•	workflow JSON placeholder 치환(`__PROMPT__`, `__NEGATIVE_PROMPT__`, `__WIDTH__`, `__HEIGHT__`, `__SEED__`, `__MODEL__`) 지원.
	•	변경 이유:
	•	Vertex/Gemini 외에 로컬 생성 경로(라이선스/비용 대응)를 운영 단계에서 선택 가능하게 하기 위함.
	•	영향 범위:
	•	yadam/gen/comfy_client.py, yadam/cli.py, docs/requirements.md
	•	비고:
	•	프로젝트 내 예시 API 워크플로우 템플릿 파일 `yadam/config/comfy_workflows/yadam_api_sdxl_placeholders.json` 추가.

[2026-02-27] comfyui 선택 시 프로젝트 기본 워크플로우 자동 사용
	•	구분: 운영/구현
	•	변경 내용:
	•	`--image-api comfyui`에서 `--comfy-workflow`와 `COMFYUI_WORKFLOW_PATH`가 모두 비어 있으면,
	•	프로젝트 기본 템플릿 `yadam/config/comfy_workflows/yadam_api_sdxl_base_fast_placeholders.json`을 자동으로 사용.
	•	최종 선택된 workflow 파일이 없으면 명시적 `FileNotFoundError`로 종료.
	•	변경 이유:
	•	초기 실행 시 workflow 경로 입력 부담을 줄이고 바로 테스트 가능하게 하기 위함.
	•	영향 범위:
	•	yadam/cli.py, docs/requirements.md

[2026-02-27] 야담용 ComfyUI 경량(base-only) 기본 워크플로우 추가
	•	구분: 설계/구현
	•	변경 내용:
	•	refiner를 제외한 SDXL base-only API 워크플로우 템플릿 `yadam/config/comfy_workflows/yadam_api_sdxl_base_fast_placeholders.json`을 추가.
	•	`--image-api comfyui` 기본 workflow를 위 템플릿으로 변경.
	•	comfyui 기본 모델을 `sd_xl_base_1.0.safetensors`로 조정.
	•	변경 이유:
	•	M1 16GB 환경에서 메모리/스왑 부담을 줄여 안정적인 장면 생성 속도를 확보하기 위함.
	•	영향 범위:
	•	yadam/config/comfy_workflows/, yadam/cli.py, docs/requirements.md

[2026-02-27] ComfyUI 기본 워크플로우에 한국 사극 화풍 고정 앵커 강화
	•	구분: 구현/튜닝
	•	변경 내용:
	•	`yadam_api_sdxl_base_fast_placeholders.json`의 positive prompt prefix를 한국 조선시대/한복/한옥/웹툰 스타일 중심으로 강화.
	•	negative prompt에 일본풍/중국풍 단서(`japanese`, `kimono`, `samurai`, `hanfu`, `qipao` 등)를 명시적으로 추가.
	•	변경 이유:
	•	실생성 결과가 일본풍/혼합풍으로 치우치는 현상을 줄이고, 야담 목적(조선시대 사극 웹툰) 방향으로 수렴시키기 위함.
	•	영향 범위:
	•	yadam/config/comfy_workflows/yadam_api_sdxl_base_fast_placeholders.json

[2026-02-27] .vrew 더미 voice 이름을 unknown으로 변경
	•	구분: 구현
	•	변경 내용:
	•	.vrew 생성 시 speaker 메타의 이름을 `tts_speaker`에서 `unknown`으로 변경.
	•	변경 이유:
	•	Vrew 후편집 단계에서 실제 음성을 수동 매핑하기 위한 더미 표기를 단순화하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py

[2026-02-27] 운영 기준 확정: 실전 기본은 Vertex, ComfyUI는 보조 실험 경로
	•	구분: 운영
	•	변경 내용:
	•	실전 품질 일관성이 중요한 기본 경로를 `vertex_imagen`으로 유지.
	•	`comfyui`는 로컬 비용/속도 실험 및 보조 생성 경로로 위치를 명확화.
	•	변경 이유:
	•	현재 로컬 SDXL 계열에서 조선시대 사극 웹툰 스타일 일관성이 충분히 확보되지 않아 운영 리스크가 높기 때문.
	•	영향 범위:
	•	docs/requirements.md(운영 권장 항목)

[2026-02-27] clips 단계 LLM scene prompt 429(RESOURCE_EXHAUSTED) 재시도 추가
	•	구분: 구현/운영
	•	변경 내용:
	•	`[6/7] clips`의 scene prompt 생성 호출에 rate-limit 전용 재시도 래퍼를 도입.
	•	`429`, `RESOURCE_EXHAUSTED`, `rate limit`, `quota` 계열 오류만 지수 백오프로 재시도(최대 4회).
	•	재시도 대기 로그(`retry in ...s`)를 출력해 진행 상태를 확인 가능하게 변경.
	•	변경 이유:
	•	Vertex 혼잡 시간대에 prompt 단계가 연속 즉시 실패하여 `_error.jpg`가 대량 생성되는 문제를 완화하기 위함.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py
	•	마이그레이션/호환:
	•	기존 산출물 스키마 변경 없음. 재실행 시부터 재시도 동작이 적용됨.

[2026-02-27] .vrew clip 분할에서 종결 조각(마침표 포함) soft merge 규칙 추가
	•	구분: 구현
	•	변경 내용:
	•	기본 clip 분할 기준은 30자를 유지하되, 다음 조각이 종결부호(`. ! ? 。 ！ ？`)로 끝나는 마무리 조각이면 합친 길이가 40자 이하일 때 앞 clip에 병합하도록 변경.
	•	의미 단위 분리뿐 아니라, 30자 초과 단일 문장의 강제 문자 분할 결과에도 동일한 soft merge를 적용.
	•	종결부호 뒤의 닫는 문자(`" ' ” ’ ) ]`)도 종결로 인정.
	•	변경 이유:
	•	`놓치지` / `않았습니다.`처럼 어색하게 잘리는 clip을 줄이고, 문장 종결부의 자연스러운 자막 단위를 유지하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 .vrew 파일에는 반영되지 않으며, 재-export한 신규 파일부터 적용됨.

[2026-02-28] .vrew clip 분할 규칙을 대사/문장/절 중심으로 재설계
	•	구분: 구현
	•	변경 내용:
	•	인용부호로 감싼 대사는 줄바꿈이 있어도 하나의 의미 단위로 병합한 뒤, 다문장 대사는 문장 경계로 clip 분할되도록 조정.
	•	서술 문장은 쉼표 절 분할을 유지하되, `그때,` 같은 짧은 도입 절은 단독 clip으로 분리되지 않도록 길이 기준을 추가.
	•	긴 대사 강제 분할 시 따옴표만 남는 clip이 생기지 않도록, 인용부호는 첫/마지막 clip에만 배치하도록 수정.
	•	변경 이유:
	•	대사/서술이 문자 수 기준으로 어색하게 잘리거나, `"`만 남는 clip이 생기는 문제를 줄이고 Vrew 편집 단위를 자연스럽게 유지하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 .vrew 파일에는 반영되지 않으며, 재-export한 신규 파일부터 적용됨.

[2026-02-28] .vrew TTS용 텍스트를 자막 텍스트와 분리하고 안전 정제 적용
	•	구분: 구현
	•	변경 내용:
	•	표시용 자막(`captions`)은 원문을 유지하고, TTS용 `ttsClipInfosMap.text.raw/processed`와 word alignment는 정제된 텍스트를 사용하도록 변경.
	•	따옴표/특수 인용부호/줄바꿈/기호를 정리하고, 내부 문장 종결부호를 일부 완화해 Vrew가 문장 단위로 과도하게 재분해하는 가능성을 낮춤.
	•	정제 후 읽을 텍스트가 남지 않는 quote-only/symbol-only chunk는 clip export 자체를 건너뛰도록 변경.
	•	변경 이유:
	•	Vrew에서 "목소리로 변환할 수 없는 특수문자" 또는 "AI 목소리로 읽어줄 텍스트가 입력되지 않았습니다" 오류로 음성 적용이 중단되는 문제를 완화하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 .vrew 파일에는 반영되지 않으며, 재-export한 신규 파일부터 적용됨.

[2026-02-28] scene prompt 웹툰 렌더링 양의 지시 강화 및 clip 스타일 앵커 보강
	•	구분: 구현/튜닝
	•	변경 내용:
	•	scene prompt LLM 규칙에 만화식 표면, 평면 색면, 선명한 윤곽선, 웹툰식 명암/톤 분리, 스타일라이즈드 얼굴/손 묘사를 명시적으로 추가.
	•	clip용 스타일 프로필 `k_webtoon_clip`에 `visible ink outlines`, `full-color cel shading`, `simplified comic surfaces`, `non-photoreal webtoon rendering` 등을 추가.
	•	변경 이유:
	•	동굴/등불/젖은 바위/혈흔 같은 장면에서 실사/영화 스틸 쪽으로 미끄러지는 현상을 줄이고, 금지문 위주가 아니라 양의 스타일 지시로 웹툰 일관성을 높이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py, yadam/config/default_profiles.yaml

[2026-02-28] scene prompt 인물 선택을 본문 등장 우선으로 변경
	•	구분: 구현
	•	변경 내용:
	•	scene prompt용 인물 선택을 `characters[:2]` 고정에서, 장면 본문에 직접 등장하는 인물/핵심 인물을 우선하는 점수 기반 선택으로 교체.
	•	`... 대감 쪽에서 사람을 보내 ...` 같은 간접 언급 인물은 감점하도록 조정.
	•	변경 이유:
	•	직접 등장하는 핵심 인물이 continuity lock에서 빠지고, 간접 언급 인물이 대신 들어가 성별/복장 일관성이 깨지는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py

[2026-02-28] 캐릭터 variant(노비/무관)별 복식 앵커와 프리셋 우선순위 수정
	•	구분: 구현
	•	변경 내용:
	•	`노비` variant에서는 `무관 도포`, `장검`, `호패`, `관복`, `갑옷` 계열 앵커를 제거하고, `거친 무명 적삼`, `해진 소매`, `단순한 허리끈` 등 하류 복식 프리셋을 우선 적용.
	•	`무관` variant에서는 반대로 `노비`, `무명 적삼`, `해진` 계열 앵커를 제거.
	•	character prompt builder에서 variant가 generic `양반/T3/상류 복식` 프리셋보다 우선하도록 override를 추가.
	•	변경 이유:
	•	안윤처럼 하나의 캐릭터가 `노비/무관` 두 상태를 가질 때 장면과 캐릭터 시트 양쪽에서 복식이 뒤섞여 일관성이 깨지는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/pipeline/orchestrator.py, yadam/prompts/builder.py

[2026-03-02] .vrew clip 따옴표 후처리 보강으로 odd quote clip 제거
	•	구분: 구현
	•	변경 내용:
	•	긴 대사를 여러 clip으로 분할할 때 각 clip이 독립적으로 따옴표를 갖도록 조정.
	•	서술문 앞에 잘못 붙은 stray quote와 이중 따옴표(`""...`)를 exporter 후처리에서 제거.
	•	변경 이유:
	•	`.vrew` 내부 captions에서 따옴표 개수가 홀수로 남아 화면 텍스트가 어색하게 보이던 clip들을 제거하기 위함.
	•	영향 범위:
	•	yadam/export/vrew_exporter.py
	•	마이그레이션/호환:
	•	기존 `.vrew`에는 반영되지 않으므로 재-export가 필요함.

[2026-03-02] `--synopsis` CLI 추가로 시놉시스 단독 생성 지원
	•	구분: 구현
	•	변경 내용:
	•	CLI에 제목/훅 직접 입력 옵션을 추가해 `--story-id` 없이도 새 스토리 번호로 시놉시스 생성을 시작할 수 있도록 변경.
	•	`prompts/make_synopsis.txt`를 프롬프트 템플릿으로 읽고, 입력 문구를 LLM(`gemini-2.5-flash`)에 전달한 뒤 `stories/storyNN.synopsis` 파일로 저장.
	•	입력 제목/훅은 `stories/storyNN.title` 파일에도 함께 저장.
	•	파일 번호는 기존 `synopsis/story*.synopsis`, 이전 규칙인 `synopsis/storyp*.synopsis`, `stories/story*.synopsis`, 그리고 `stories/story*.txt`의 최대 번호를 기준으로 다음 값을 사용.
	•	변경 이유:
	•	스토리 본문 생성과 분리해서, 제목/훅 한 줄로 시놉시스 초안을 빠르게 만들 수 있게 하기 위함.
	•	영향 범위:
	•	yadam/cli.py
	•	마이그레이션/호환:
	•	현재 표면 옵션명은 `--title`이며, 이전 `--synopsis`는 숨김 호환 별칭으로만 유지됨.

[2026-03-02] `--story-id` 기반 시놉시스 생성 흐름으로 CLI 분기 조정
	•	구분: 구현
	•	변경 내용:
	•	`python -m yadam.cli --story-id story06` 실행 시 기본 흐름을 interactive하게 재구성.
	•	1) `stories/story06.title`을 읽어 `stories/story06.synopsis` 생성 -> 확인 `(Y/n, 기본 Y)`.
	•	2) `stories/story06.synopsis`를 읽어 `stories/story06.txt` 생성 -> 확인 `(Y/n, 기본 Y)`.
	•	3) `stories/story06.txt`를 입력으로 기존 이미지 생성 및 `.vrew` export 파이프라인 실행.
	•	`--non-interactive` 모드에서는 위 절차를 확인 없이 처음부터 끝까지 자동 실행.
	•	`--make_synopsis` 옵션은 `stories/storyNN.title -> stories/storyNN.synopsis` 단계만 수행.
	•	`--make-story [500|1000]` 옵션을 추가해 `stories/storyNN.synopsis`를 입력으로 `stories/storyNN.txt`를 생성하도록 확장.
	•	`--make-story`는 synopsis를 `N챕터: 제목` 형식으로 파싱한 뒤, 챕터별로 LLM을 순차 호출해 `storyNN.txt`에 누적 저장한다.
	•	값을 생략하면 기본 분량은 챕터당 `500`자, `1000` 지정 시 챕터당 `1000`자 내외를 목표로 한다.
	•	기존 story 파일이 있으면 interactive 모드에서는 덮어쓸지 확인하고, `--non-interactive`에서는 확인 없이 덮어쓴다.
	•	챕터 생성 실패 시 같은 챕터를 최대 3회 재시도하고, 그래도 실패하면 중단한다.
	•	다음 실행 시에는 기존 `storyNN.txt`의 마지막 성공 챕터를 읽어 그 다음 챕터부터 재개한다.
	•	synopsis와 story chapter는 저장 전에 최소 형식 보정을 거친다.
	•	synopsis: 코드블록 제거, 줄바꿈 정리, `N챕터: 제목` 형식 정규화.
	•	story: 코드블록/설명문 제거, `Chapter N : 제목` 헤더 강제, 본문 공백 줄 정리.
	•	변경 이유:
	•	작업 흐름을 `title -> synopsis -> story -> images`로 분리해 단계별 검토와 재실행을 단순화하고, Gemini의 긴 출력 한계를 챕터 단위 생성으로 우회하기 위함.
	•	영향 범위:
	•	yadam/cli.py, prompts/make_story.txt
	•	마이그레이션/호환:
	•	기본 `--story-id`는 다시 전체 파이프라인을 수행하며, 단계별 단독 실행은 `--make_synopsis`, `--make-story`로 분리됨.

[2026-03-02] `--title` 입력과 hash 기반 skip 규칙 추가
	•	구분: 구현
	•	변경 내용:
	•	제목/훅 직접 입력 옵션의 표면 이름을 `--synopsis`에서 `--title`로 변경하고, 이전 이름은 숨김 호환 별칭으로 유지.
	•	`python -m yadam.cli --title "..." --non-interactive` 실행 시 새 `stories/storyNN.title` 생성 후 `synopsis -> story -> 이미지/.vrew`까지 자동으로 이어지도록 정리.
	•	`stories/.storyNN.title.sha256`를 사용해 `--non-interactive`에서 title 내용이 바뀐 경우에만 synopsis를 재생성.
	•	`stories/.storyNN.story_source.sha256`를 사용해 synopsis 내용이 바뀐 경우에만 story를 재생성하고, 같으면 완료본 skip 또는 중간 실패 지점부터 재개.
	•	synopsis와 story 출력, 그리고 hash sidecar는 원자적으로 저장되도록 변경.
	•	변경 이유:
	•	비대화형 실행에서 불필요한 재생성을 줄이고, 중간 실패 후에도 입력 기준이 바뀌지 않았다면 안전하게 이어서 실행하기 위함.
	•	영향 범위:
	•	yadam/cli.py

[2026-03-02] `make_story` 분량 기준을 제목 제외 본문 기준으로 명시
	•	구분: 프롬프트
	•	변경 내용:
	•	`prompts/make_story.txt`에 500자/1,000자 분량 규정은 `Chapter N : ...` 제목 라인을 제외한 본문 기준이라는 점을 명시.
	•	글자 수 정의, 30분/1시간 분량 설명, 실전 출력 규칙에 동일 기준을 반영.
	•	변경 이유:
	•	자동 생성된 chapter의 제목 길이에 따라 목표 분량 판정이 흔들리지 않도록 하기 위함.
	•	영향 범위:
	•	prompts/make_story.txt

[2026-03-02] `주먹밥` 소품을 조선식 둥근 밥덩이로 고정
	•	구분: 프롬프트
	•	변경 내용:
	•	scene text에 `주먹밥`이 있으면 prompt builder에서 조선식 손주먹밥 소품 고증 문구를 추가.
	•	LLM scene prompt 규칙에 `주먹밥`은 일본식 삼각 오니기리가 아니라 둥글고 투박한 조선식 밥덩이, 김 띠 없음, 헝겊/소반/손 위의 소박한 형태로 묘사하도록 명시.
	•	변경 이유:
	•	조선시대 음식 소품이 일본식 onigiri 형태로 잘못 일반화되는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/prompts/builder.py, yadam/nlp/llm_scene_prompt.py

[2026-03-02] CLI 진행 로그 및 텍스트 LLM 백오프 재시도 추가
	•	구분: 구현
	•	변경 내용:
	•	`--title`, `--story-id`, `--make_synopsis`, `--make-story` 실행 시 synopsis 생성, story 생성, 이미지/.vrew 파이프라인 단계가 `[INFO] step N/M` 로그로 즉시 출력되도록 추가.
	•	synopsis 생성 직전 `synopsis LLM request -> gemini-2.5-flash`, chapter 생성 직전 `chapter LLM request -> gemini-2.5-flash (Chapter N)` 로그를 추가.
	•	synopsis 생성에도 최대 3회 백오프 재시도(1.5s -> 3.0s -> 6.0s)를 추가.
	•	story chapter 생성의 기존 3회 재시도에도 같은 백오프를 추가하고, `500/502/503/504`, `INTERNAL`, `RESOURCE_EXHAUSTED`, `timeout` 등을 transient 오류로 판별하도록 보강.
	•	변경 이유:
	•	비대화형 실행에서 멈춘 것처럼 보이는 구간을 줄이고, Gemini API의 일시적 서버 오류가 바로 전체 실패로 이어지지 않게 하기 위함.
	•	영향 범위:
	•	yadam/cli.py

[2026-03-02] Gemini 이미지 경로 호환성 및 진단 로그 보강
	•	구분: 구현
	•	변경 내용:
	•	이미지 파이프라인 시작 시 `image_api`, `image_model`과 함께 실제 선택된 `image_client` 클래스명을 출력하도록 추가.
	•	`VertexImagenClient`가 Gemini API 환경에서 `negative_prompt parameter is not supported in Gemini API` 오류를 반환하면, 동일 요청을 `negative_prompt` 없이 한 번 더 시도하도록 보강.
	•	기존 실패 scene을 재시도할 수 있도록 `story07` 초반 clip error 상태를 재초기화.
	•	변경 이유:
	•	Gemini API 사용 시 Vertex용 `negative_prompt` 설정이 호환성 오류를 내는 경우를 완화하고, 현재 어떤 이미지 클라이언트가 실제로 사용되는지 로그에서 바로 확인할 수 있게 하기 위함.
	•	영향 범위:
	•	yadam/gen/gemini_client.py, yadam/cli.py

[2026-03-02] scene prompt를 shot-first 경량 규칙으로 재구성
	•	구분: 프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py`의 system 지시를 레퍼런스 보드용 짧은 영어 연출문, 첫 문장은 샷/카메라 지시로 시작하는 shot-first 형식으로 강화.
	•	공통 규칙 배열을 짧게 압축해 boilerplate 비중을 줄이고, 장면 핵심 시각 정보(인물 1~2명, 행동 1개, 배경 1개, 분위기 1개) 중심으로 prompt를 유도.
	•	`포졸`, `주먹밥` 관련 규칙은 `scene_text`, 장소, 인물 정보에 해당 키워드가 있을 때만 삽입하도록 조건부 규칙으로 분리.
	•	변경 이유:
	•	Gemini 이미지 경로에서 긴 제약문보다 장면 핵심 연출이 우선되도록 하고, 드문 규칙이 모든 scene에 반복 삽입되며 토큰을 늘리는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py

[2026-03-02] Gemini image API에 실제 16:9 aspect ratio 설정 전달
	•	구분: 구현
	•	변경 내용:
	•	`GeminiFlashImageClient`가 `generate_content(..., image_config=ImageConfig(aspect_ratio=...))`를 사용하도록 변경.
	•	기존의 텍스트 힌트 `[output constraint] aspect ratio: 16:9`와 별도로 SDK의 실제 이미지 설정값으로 `aspect_ratio`를 전달.
	•	변경 이유:
	•	Gemini 이미지 경로에서도 16:9 비율을 단순 프롬프트 힌트가 아니라 API 설정으로 강제하기 위함.
	•	영향 범위:
	•	yadam/gen/gemini_client.py

[2026-03-03] synopsis Markdown 헤더를 챕터 형식으로 정규화
	•	구분: 구현
	•	변경 내용:
	•	`cli.py`의 synopsis 정규화/파서가 `## ...` 제목 줄과 `**1챕터: 제목**` 같은 Markdown 헤더를 정리하고, 최종적으로 `N챕터: 제목` 형식으로 인식하도록 보강.
	•	기존 plain text 형식뿐 아니라 bold/heading 장식이 포함된 synopsis도 그대로 story 생성 단계로 넘길 수 있게 함.
	•	변경 이유:
	•	Gemini가 synopsis를 Markdown 스타일로 반환해도 후속 `--make-story` 단계가 `N챕터: 제목` 형식을 안정적으로 파싱하도록 하기 위함.
	•	영향 범위:
	•	yadam/cli.py

[2026-03-03] scene prompt에서 직접 대사/인용문 사용 금지
	•	구분: 프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py` 공통 규칙에 직접 대사와 인용부호 사용 금지를 추가.
	•	`shouting "..."`, `saying "..."` 같은 직접 발화문 대신 `mouth open in a forceful shout`, `appears to be announcing his authority`처럼 입 모양, 표정, 제스처 중심의 행동 묘사를 사용하도록 지시.
	•	변경 이유:
	•	scene prompt 안의 직접 대사/인용부호가 Gemini 이미지에서 말풍선, 글자, lettering을 유도하는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py

[2026-03-03] make-story 프롬프트에 대사 높임말 일관성 규칙 추가
	•	구분: 프롬프트
	•	변경 내용:
	•	`make_story.txt`에 화자-청자 관계에 맞는 호칭과 종결어미를 일치시키는 규칙을 추가.
	•	반말 호칭(`이안아`, `너`, `네가`)과 `-입니다`체 혼용을 금지하고, 높임 관계(`나으리`, `마님`, `소인`)는 그에 맞는 존대 종결로 유지하도록 명시.
	•	변경 이유:
	•	대사 생성 시 호칭은 낮춤인데 종결은 존댓말인 부자연스러운 문장을 줄이고, 인물 관계에 맞는 화법 일관성을 확보하기 위함.
	•	영향 범위:
	•	prompts/make_story.txt

[2026-03-03] Gemini clip 이미지에 캐릭터 reference image 첨부
	•	구분: 구현
	•	변경 내용:
	•	이미지 요청 객체에 `reference_image_paths`를 추가하고, clip 생성 시 scene의 핵심 캐릭터 1~2명의 캐릭터 이미지를 함께 전달하도록 변경.
	•	`GeminiFlashImageClient`는 reference image를 실제 `parts`로 첨부하고, 동일한 얼굴/헤어/복식 실루엣과 core identity anchors를 유지하라는 제약문을 prompt에 추가.
	•	변경 이유:
	•	Gemini 이미지 생성에서 텍스트 continuity lock만으로 부족했던 인물 일관성을 실제 캐릭터 reference image 기반으로 보강하기 위함.
	•	영향 범위:
	•	yadam/gen/image_client.py, yadam/gen/image_tasks.py, yadam/gen/gemini_client.py, yadam/pipeline/orchestrator.py

[2026-03-03] 조선 주거 실내의 온돌/아궁이 고증 규칙 추가
	•	구분: 프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py`에 조선시대 주거 실내는 온돌 구조를 우선하고, 일반 생활방 안에 노출된 실내 화덕/벽난로를 만들지 않도록 규칙을 추가.
	•	아궁이는 부엌 쪽 난방 구조나 식은 재, 구들 온기 같은 간접 표현으로 번역하도록 유도.
	•	변경 이유:
	•	실내 생활방 장면에서 현대식 벽난로나 방 안 노출 아궁이처럼 잘못된 구조가 생성되는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py

[2026-03-03] 비참한 상황을 기괴한 얼굴/신체 왜곡으로 과장하지 않도록 규칙 추가
	•	구분: 프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py` 공통 규칙에 굶주림, 질병, 절망, 혹한 같은 상황은 공포물처럼 기괴한 얼굴이나 과장된 신체 왜곡으로 표현하지 않도록 추가.
	•	수척함과 궁핍은 마른 실루엣, 해진 옷, 황량한 환경, 절제된 표정으로 전달하도록 유도.
	•	변경 이유:
	•	혹한·기근 장면에서 Gemini가 인물 얼굴과 신체를 과하게 왜곡해 기괴하게 그리는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py

[2026-03-04] scene prompt에 학령기 아동/인원 수/서양식 벽난로 금지 규칙 추가
	•	구분: 프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py` 공통 규칙에 5~7세 아동은 갓난아기나 포대기 아기가 아닌 학령기 어린이 비율로 유지하도록 추가.
	•	장면에 `두 아이`, `남매`처럼 인원 수가 명시되면 정확히 그 수만 묘사하고 여분의 아이를 추가하지 않도록 추가.
	•	조선시대 실내 난방 관련 규칙에 서양식 `fireplace`, `wall hearth`, `stone hearth`를 명시적으로 금지하고, 화로/부엌 쪽 솥/온돌 기척 같은 조선식 난방 소품으로 번역하도록 강화.
	•	변경 이유:
	•	남매 장면에서 아이 수가 과장되거나 성별이 섞이고, 실내 장면이 서양식 벽난로로 잘못 해석되는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py

[2026-03-04] 인물/장소 태깅을 alias 기반으로 보강하고 scene backfill 추가
	•	구분: 구현
	•	변경 내용:
	•	`entity_extract.py`의 fallback `Character` 구조에 `aliases` 필드를 추가해 이름 변형을 다룰 수 있게 확장.
	•	`tagger.py` 기본 태깅이 canonical name만 보던 방식에서 canonical+aliases 매칭으로 확장.
	•	`llm_extract.py` 요구사항을 강화해 실명이 있을 때 역할명보다 실명을 canonical로 우선하고, 역할/호칭은 aliases로 흡수하도록 명시.
	•	`orchestrator.py` scene merge 단계에서 LLM scene tag가 비어 있거나 약할 때 `scene.text`를 canonical+aliases로 재스캔해 `characters`, `places`, `character_instances`를 backfill하도록 추가.
	•	변경 이유:
	•	새 story에서 scene `characters=[]`가 과도하게 발생하고 역할명/실명이 분리되어 인물 일관성이 깨지는 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/entity_extract.py, yadam/nlp/tagger.py, yadam/nlp/llm_extract.py, yadam/pipeline/orchestrator.py

[2026-03-04] 세션 운영 문서(AGENTS.md) 추가
	•	구분: 문서
	•	변경 내용:
	•	다음 세션에서 에이전트가 우선 참조할 역할/우선순위/에러 대응 기준 문서를 추가.
	•	커밋 요청 시 기본적으로 같은 턴에서 push까지 연속 수행하는 운영 규칙을 명시.
	•	변경 이유:
	•	세션 간 작업 방식과 품질 기준을 일관되게 유지하기 위함.
	•	영향 범위:
	•	AGENTS.md

[2026-03-07] clip 동적 연출/고채도 기본, 동물 캐릭터(누렁이=소) 고정, 장소 서사성 강화
	•	구분: 구현+프롬프트
	•	변경 내용:
	•	`llm_scene_prompt.py` 공통 규칙을 강화해 정적 구도를 줄이고, 표정/제스처/행동 중간 동작을 반드시 포함하도록 조정.
	•	대본에 야간 명시가 없으면 낮(daytime)을 기본으로 두고, 밝은 노출 + 중고채도 + 명확한 대비를 지시하도록 추가.
	•	시장/장터/마을/관아 문맥에서는 배경 군중/생활 동선을 넣어 생동감을 높이도록 조건부 규칙 추가.
	•	누렁이/소 관련 장면에서 `소(cattle)` 해부학을 고정하고 개(canine)로 바뀌지 않도록 조건부 규칙 추가.
	•	`llm_extract.py`에 캐릭터 `species` 필드를 추가하고, 반복 등장 동물도 캐릭터로 추출하도록 요구사항 강화.
	•	`orchestrator.py`에서 `species`를 project 캐릭터 메타에 저장/전파하고, 장면 프롬프트/캐릭터 프롬프트 생성 시 species를 전달하도록 반영.
	•	`entity_extract.py` 규칙 기반 후보에 `누렁이`, `황소`를 추가해 LLM 실패 폴백에서도 동물 캐릭터 누락을 줄임.
	•	`build_place_prompt()`를 조정해 장소 컷에 문맥형 생활 요소(사람/군중/동물)를 적정량 허용하고, 기본 시간대를 낮으로 유도.
	•	변경 이유:
	•	`story11` 비교에서 드러난 클립 정적 연출, 저채도/야간 편중, 동물 캐릭터 오인식(소→개), 배경 서사성 부족 문제를 줄이기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_scene_prompt.py, yadam/nlp/llm_extract.py, yadam/pipeline/orchestrator.py, yadam/prompts/builder.py, yadam/nlp/entity_extract.py, docs/changes.md

[2026-03-07] 2차 LLM 추출을 1000자 청크 다회 호출 방식으로 변경
	•	구분: 구현
	•	변경 내용:
	•	`LLMEntityExtractor`를 단일 대본 요청 방식에서 `chunk_chars=1000` 기준의 다회 호출 방식으로 변경.
[2026-03-11] 텍스트 Gemini 기본 모델을 `gemini-3-flash-preview`로 승격하고 CLI override 추가

- 목적
	- 기존 `gemini-2.5-flash` 하드코딩을 줄이고, 새 Gemini 계열 모델을 synopsis/story/scene 관련 전 경로에서 일관되게 사용할 수 있게 하기 위함.
- 변경
	- `yadam/model_defaults.py`
	- 텍스트/이미지 기본 모델 상수 추가.
	- `yadam/cli.py`
	- `--llm-model` 옵션 추가.
	- synopsis 생성, chapter 생성, 전체 파이프라인 실행 시 동일한 텍스트 LLM 모델을 전달하도록 변경.
	- 실행 로그에 `llm_model=...` 출력 추가.
	- `yadam/pipeline/orchestrator.py`
	- scene prompt, prompt rewrite, scene binding, entity extract 단계가 `PipelineConfig.llm_model`을 사용하도록 변경.
	- `yadam/nlp/llm_scene_prompt.py`, `yadam/nlp/llm_prompt_rewrite.py`, `yadam/nlp/llm_scene_binding.py`, `yadam/nlp/llm_extract.py`
	- 텍스트 LLM 기본값을 중앙 상수로 통일.
	- `yadam/gen/gemini_client.py`
	- 이미지 기본 모델도 중앙 상수를 사용하도록 정리.
	- `docs/cli_usage.md`, `docs/requirements.md`
	- `--llm-model` 사용법과 기본값 문서화.
- 참고
	- 요청 표현의 `gemini 3.1 fast`와 달리, 현재 코드에 추가한 공식 모델명은 `gemini-3-flash-preview` 기준이다.
- 검증
	- `python -m py_compile yadam/cli.py yadam/model_defaults.py yadam/pipeline/orchestrator.py yadam/nlp/llm_scene_prompt.py yadam/nlp/llm_prompt_rewrite.py yadam/nlp/llm_scene_binding.py yadam/nlp/llm_extract.py yadam/gen/gemini_client.py`

[2026-03-11] `--through-tag-scene` 추가: tag_scene까지의 Python 전처리만 수행

- 목적
	- story 파일이 이미 있을 때, LLM 구조 추출과 이미지 생성 없이 Python 전처리(scene split + seed 추출 + `tag_scene`)까지만 실행할 수 있게 하기 위함.
- 변경
	- `yadam/cli.py`
	- `--through-tag-scene` 옵션 추가.
	- 실행 로그에 `through_tag_scene` 상태 출력 추가.
	- `yadam/pipeline/orchestrator.py`
	- `PipelineConfig.stop_after_tag_scene` 추가.
	- `reuse_scenes` 경로와 fresh split 경로 모두에서 `stop_after_tag_scene`면 LLM extract 이전에 중단하도록 변경.
	- 이 모드에서는 `project.project.llm_extract`를 skipped로 기록하고, `phase_detail`을 `through_tag_scene`로 저장.
	- `docs/cli_usage.md`
	- 사용 예시 추가.
- 검증
	- `python -m py_compile yadam/cli.py yadam/pipeline/orchestrator.py`

[2026-03-11] `--through-place-refs` 추가: 7/8단계 레퍼런스 생성까지만 수행

- 목적
	- 캐릭터/장소 레퍼런스 이미지 생성만 끝내고, clip 생성과 export 전에 안정적으로 중단할 수 있게 하기 위함.
- 변경
	- `yadam/cli.py`
	- `--through-place-refs` 옵션 추가.
	- 실행 로그에 `through_place_refs` 상태 출력 추가.
	- `yadam/pipeline/orchestrator.py`
	- `PipelineConfig.stop_after_place_refs` 추가.
	- 장소 생성 단계 직후 `stop_after_place_refs`면 `phase=refs_ready`, `phase_detail=through_place_refs`를 저장하고 중단하도록 변경.
	- `docs/cli_usage.md`
	- 사용 예시 추가.
- 검증
	- `python -m py_compile yadam/cli.py yadam/pipeline/orchestrator.py`

[2026-03-11] Gemini 이미지 모델 호환성 보정: `gemini-3-flash-preview` 요청 시 지원 모델로 fallback

- 목적
	- `gemini-3-flash-preview`가 이미지 생성 지원 모델이 아니어서 400 오류가 발생하므로, Gemini 이미지 경로를 지원 모델로 안정화하기 위함.
- 변경
	- `yadam/model_defaults.py`
	- `DEFAULT_GEMINI_IMAGE_MODEL`을 `gemini-2.5-flash-image`로 복구.
	- `gemini-3-flash-preview` 요청 시 `gemini-2.5-flash-image`로 보정하는 fallback 함수 추가.
	- `yadam/cli.py`, `yadam/gen/gemini_client.py`
	- Gemini 이미지 모델 요청값을 보정하고 warning을 출력하도록 변경.
	- `docs/cli_usage.md`, `docs/requirements.md`
	- Gemini 이미지 기본 모델 예시와 요구사항 문구를 지원 모델 기준으로 갱신.
- 검증
	- `python -m py_compile yadam/model_defaults.py yadam/gen/gemini_client.py yadam/cli.py`

	•	대본을 겹침(overlap) 포함 청크로 분할하고, 각 청크마다 해당 구간과 겹치는 scene 요약만 선택해 LLM에 전달.
	•	청크 분할은 단순 글자 슬라이딩이 아니라 문장 경계(마침표/물음표/느낌표/줄바꿈) 기준으로 근사 1000자를 맞추도록 보강.
	•	청크별 결과를 병합하도록 로직 추가:
	•	캐릭터/장소는 canonical name 기준 dedup + aliases/anchors/traits/variants union 병합.
	•	scene_tags는 scene_id 기준으로 characters/places/character_instances를 set 병합.
	•	`LLMExtractorConfig.max_script_chars` 기본값을 0(전체 대본 사용)으로 변경.
	•	변경 이유:
	•	긴 대본에서 앞부분 편향을 줄이고, 캐릭터/장면 정보 추출 범위를 대본 전체로 확장하기 위함.
	•	영향 범위:
	•	yadam/nlp/llm_extract.py, docs/changes.md
[2026-03-07] .vrew export에 voice/style preset 반영(Story10 수동 편집값 기준)

- 목적
	- 수동 편집한 `.vrew`(voice id/volume/speed/pitch, caption style) 값을 다음 자동 export에도 동일하게 반영.
- 변경
	- `yadam/export/vrew_exporter.py`
	- 기본 export preset을 KT `vos-female28`(ko-KR, middle, emotion neutral, volume 0, speed 0, pitch -1)로 설정.
	- `globalCaptionStyle` 기본값을 Story10 편집본과 동일한 스타일(`Pretendard-Vrew_700`, outline 포함)로 설정.
	- `ttsClipInfosMap` 각 clip에도 동일 speaker/volume/speed/pitch/emotion을 기록.
	- 같은 story의 기존 `out/<story>.vrew`가 존재하면 내부 `project.json`의 `lastTTSSettings`/`globalCaptionStyle`를 우선 재사용.
	- 환경변수 `VREW_TEMPLATE_PATH`가 지정되면 해당 `.vrew`를 preset 소스로 우선 사용.
- 검증
	- `python -m py_compile yadam/export/vrew_exporter.py` 통과.
	- `work/story10/out/project.json`로 임시 export 후, 결과 `project.json`에서 `version=16`, `lastTTSSettings`, `ttsClipInfosMap[*]`, `globalCaptionStyle` 반영 확인.
[2026-03-07] story11 점검 이슈 대응: 돌쇠 누락 / 누렁이 종 오판별 보강

- 증상
	- `work/story11/out/project.json`에서 `llm_extract` 실패(`additionalProperties is not supported in the Gemini API.`).
	- 그 결과 규칙 기반 폴백으로 내려가며 캐릭터가 역할명 위주(`도령/마님/...`)로 구성되어 `돌쇠` 누락.
	- `누렁이`가 `species=기타`로 남아 캐릭터 프롬프트의 소(cattle) 강제 규칙이 약해짐.
- 원인
	- `yadam/nlp/llm_extract.py`의 response schema에 `List[Dict[str,str]]`(`scene_tags.character_instances`)가 포함되어 Gemini response_schema 제약과 충돌.
	- 폴백 추출기(`entity_extract.py`)의 실명 후보가 부족해 `돌쇠`를 안정적으로 잡지 못함.
- 수정
	- `yadam/nlp/llm_extract.py`
	- `LLMSceneTag.character_instances`를 `Dict` 대신 고정 모델(`name`, `variant`) 리스트로 변경해 schema 제약 회피.
	- `yadam/nlp/entity_extract.py`
	- 폴백 실명 힌트에 `돌쇠`, `연화`, `최 서리` 추가.
	- `yadam/pipeline/orchestrator.py`
	- `_infer_species`에 `script_text` 문맥 인자 추가.
	- `누렁이`는 대본 전체 문맥(외양간/쟁기/고삐/발굽 vs 개집/짖다/꼬리) 카운트로 소/개를 판별.
	- merge/fallback 경로 모두 `clean_text`를 전달해 종 판별 일관성 강화.
- 검증
	- `py_compile` 통과:
		- `yadam/nlp/llm_extract.py`
		- `yadam/nlp/entity_extract.py`
		- `yadam/pipeline/orchestrator.py`
	- 폴백 추출 결과에서 `돌쇠` 포함 확인(`extract_characters`).
	- `LLMExtractionResult.model_json_schema()` 기준 `additionalProperties` 키 없음 확인.
[2026-03-07] 2차 LLM(1,000자 chunk) 단계에서 scene별 clip 프롬프트 동시 생성

- 목적
	- 캐릭터/장소 추출 시점(2차 LLM chunk 분석)에서 scene별 clip image prompt를 함께 생성해, clip 단계의 추가 LLM 호출을 줄이고 문맥 일관성을 높임.
- 변경
	- `yadam/nlp/llm_extract.py`
	- LLM 응답 스키마에 `scene_prompts[{scene_id, prompt}]` 추가.
	- chunk 요청 요구사항에 scene별 짧은 영어 clip prompt 생성 규칙 추가.
	- chunk merge 시 `scene_id` 기준으로 prompt를 취합(정보량이 큰 prompt 우선).
	- `yadam/pipeline/orchestrator.py`
	- scene 레코드에 `llm_clip_prompt` 필드 추가.
	- 구조 merge 시 `llm_out.scene_prompts`를 `scene.llm_clip_prompt`로 저장.
	- clip 생성 단계에서 `scene.llm_clip_prompt`가 있으면 우선 사용하고, 없을 때만 기존 `LLMScenePromptBuilder` 호출.
- 검증
	- `python -m py_compile yadam/nlp/llm_extract.py yadam/pipeline/orchestrator.py` 통과.

[2026-03-10] story14 "박 노인" 이름-이미지 매핑 점검 결과 문서화

- 구분
	- 운영 문서화
- 변경 내용
	- `docs/cli_usage.md`에 "이름-이미지 매핑 점검(Story14: 박 노인 사례)" 섹션 추가.
	- 점검 결과를 문서로 고정:
		- `project.json`에서 `char_004(name=박 노인)`가 `char_004_박_노인_노년.jpg`와 연결됨.
		- scene 텍스트의 `"박 노인"` 구간에서 `scene.characters`/`scene.character_instances`에 `char_004`가 반영됨.
	- 코드 동작 기준을 문서로 명시:
		- `_apply_scene_bindings()`의 이름→`char_id` 매핑 기준(`strip()` 적용).
		- 클립 참조 이미지 선택 시 `character_instances.variant` 우선, 없으면 기본 `image.path` fallback.
	- 재점검용 CLI 명령(빠른 확인 스니펫) 추가.
- 변경 이유
	- story14 운영 중 제기된 `"박 노인"` 연결 안정성 질문에 대해, 동일 기준으로 재검증 가능하도록 운영 문서에 고정하기 위함.
[2026-03-11] make_vrew skill에 clip prompt 점검 + 9단계(stop before export) 경로 추가

- 목적
	- `make_vrew` hybrid workflow가 step 8에서 멈추지 않고, Codex가 clip prompt를 먼저 검수한 뒤 step 9 clip 생성까지만 안전하게 진행하도록 확장.
- 변경
	- `yadam/cli.py`
		- `--through-clips` 옵션 추가.
	- `yadam/pipeline/orchestrator.py`
		- `PipelineConfig.stop_after_clips` 추가.
		- clip 생성 완료 직후 `stop_after_clips`면 `project.phase=clips_ready`, `phase_detail=through_clips` 저장 후 export 전에 중단.
	- `skills/make_vrew/SKILL.md`
		- step 9 전 Codex clip prompt review 단계 추가.
		- step 9 실행 후 clip 에러까지 자동 점검하도록 흐름 확장.
	- `skills/make_vrew/scripts/review_clip_prompts.py`
		- `llm_clip_prompt`에서 대사형/visible text 유도 패턴을 탐지하는 점검 스크립트 추가.
	- `skills/make_vrew/scripts/run_through_clips.sh`
		- `python -m yadam.cli --story-id <id> --through-clips --non-interactive --image-api gemini_flash_image` 래퍼 추가.
	- `skills/make_vrew/references/clip_prompt_review.md`
		- Codex 수동 검수 기준 추가.
	- `docs/cli_usage.md`
		- `--through-clips` 사용법 문서화.
- 이유
	- clip 단계는 이미지 생성 전 마지막 텍스트 제어 지점이라, 대사/캡션 유도 프롬프트를 Codex가 사전 정리하는 운영 흐름이 필요함.

[2026-03-11] make_vrew skill에서 clip 전부 성공 시 Python export 자동 연결

- 목적
	- hybrid workflow가 step 9 clip 성공 후 수동 개입 없이 Python `.vrew` export까지 이어지도록 정리.
- 변경
	- `skills/make_vrew/SKILL.md`
		- step 9 이후 clip 에러가 없으면 export를 자동 수행하도록 절차 추가.
	- `skills/make_vrew/scripts/run_export_after_clips.sh`
		- 일반 CLI를 non-interactive로 재실행해 기존 산출물을 재사용하면서 export 단계만 자연스럽게 통과하도록 래퍼 추가.
- 이유
	- 현재 CLI는 clip 완료 상태에서 재실행하면 export만 남는 구조이므로, 별도 export 전용 파라미터 없이도 안정적으로 Python export를 수행할 수 있음.

[2026-03-11] CLI 진행 출력 stdout/stderr를 story별 logs 파일에도 tee

- 목적
	- 기존 `print` 기반 진행 상황을 콘솔에서만 보지 않고 `work/<story-id>/logs/` 아래 파일로도 남겨 실행 추적과 사후 점검을 쉽게 하기 위함.
- 변경
	- `yadam/cli.py`
		- `_TeeWriter`, `_enable_run_log()` 추가.
		- `story-id`가 결정되면 `work/<story-id>/logs/<story-id>.log`에 stdout/stderr를 함께 기록하도록 변경.
- 이유
	- 오케스트레이터와 CLI 전반이 `print` 중심이므로, 개별 로깅 호출을 뜯어고치지 않고도 story 단위 실행 로그를 안정적으로 남길 수 있음.

[2026-03-11] shared `rules/` fallback 제거, 폴더를 `docs_user/`로 전환

- 목적
	- 현재 continuity rule 운영 기준이 `stories/<story-id>_*.yaml`로 정리되어 있으므로, 더 이상 사용하지 않는 shared `rules/*.yaml` fallback과 폴더를 정리.
- 변경
	- `yadam/pipeline/orchestrator.py`
		- `rules/variant_overrides.yaml`, `rules/scene_bindings.yaml` fallback 로드 제거.
		- 관련 주석을 story-specific YAML 기준으로 수정.
	- `docs/cli_usage.md`, `skills/yadam-structure-rules/SKILL.md`
		- `rules/` fallback 설명 제거.
	- `rules/` 아래 YAML 파일 삭제 후 폴더명을 `docs_user/`로 변경.
- 이유
	- 실제 운영 흐름은 story별 YAML을 source of truth로 사용하고 있어 shared fallback이 오히려 혼동을 만들기 때문.

[2026-03-11] make_vrew skill에 7/8단계 후 캐릭터 레퍼런스 점검 게이트 추가

- 목적
	- clip 단계 진입 전에 캐릭터 reference 이미지의 메타/파일 상태와 기본 continuity 품질을 먼저 확인해 잘못된 reference가 clip 생성에 전파되지 않도록 하기 위함.
- 변경
	- `skills/make_vrew/SKILL.md`
		- step 8 뒤에 character reference review 단계를 추가.
		- 문제 발견 시 step 9를 중단하고 재생성 대상만 보고하도록 규칙 추가.
	- `skills/make_vrew/scripts/check_character_refs.py`
		- `project.json`의 character image meta/path/status와 stale `_error.jpg`를 검사하는 자동 점검 스크립트 추가.
	- `skills/make_vrew/references/character_ref_review.md`
		- Codex가 육안으로 확인할 continuity/variant/visible-text 기준 정리.
- 이유
	- story14 운영에서 인물 variant, 이름-이미지 연결, stale error file, reference 품질이 clip 단계 결과에 직접 영향을 준다는 점이 확인되었기 때문.

[2026-03-11] make_vrew skill에 9단계 후 clip 이미지 점검 게이트 추가

- 목적
	- clip 생성 후 흰 배경/과다 밝기/파일 상태 이상 같은 저품질 clip을 export 전에 걸러내기 위함.
- 변경
	- `skills/make_vrew/SKILL.md`
		- step 9 후 clip image review 단계를 추가하고, 문제가 있으면 export를 중단하도록 규칙 강화.
	- `skills/make_vrew/scripts/check_clip_images.py`
		- clip 메타/파일 존재/stale error file과 밝기·white ratio를 기반으로 suspicious clip을 자동 탐지하는 스크립트 추가.
	- `skills/make_vrew/references/clip_image_review.md`
		- Codex가 육안으로 확인할 clip 품질 기준 정리.
- 이유
	- 실제 운영에서 일부 clip이 흰 배경처럼 보이는 사례가 있어, export 이전의 품질 게이트가 필요했기 때문.

[2026-03-11] make_vrew step 9 전 clip prompt review에 place/환경 cue 부족 차단 규칙 추가

- 목적
	- `places=[]` 상태와 지나치게 generic한 clip prompt 때문에 흰 배경/무대형 clip이 나오는 문제를 step 9 전에 차단하기 위함.
- 변경
	- `skills/make_vrew/scripts/review_clip_prompts.py`
		- `generic_prompt`, `missing_place_tag`, `missing_environment_cue`를 탐지하도록 강화.
	- `skills/make_vrew/references/clip_prompt_review.md`
		- concrete environment cue와 place grounding을 필수 review 기준으로 추가.
	- `skills/make_vrew/SKILL.md`
		- generic prompt와 place/environment 부족 scene은 step 9 전에 반드시 보강하도록 규칙 추가.
- 이유
	- story14의 특정 clip들이 place reference가 비어 있고 prompt도 generic해서 사실상 흰 배경 standing shot으로 수렴한 사례가 확인되었기 때문.

[2026-03-11] make_vrew step 9 전 flagged scene은 Codex가 직접 보강 후 진행하도록 전환

- 목적
	- place 누락이나 generic prompt를 발견했을 때 단순 차단으로 끝내지 않고, Codex가 `project.json`을 보강해 step 9까지 이어서 진행하도록 workflow를 강화.
- 변경
	- `skills/make_vrew/SKILL.md`
		- clip prompt review 단계에서 flagged scene을 직접 repair한 뒤 재검사 후 진행하도록 절차 수정.
	- `skills/make_vrew/references/clip_prompt_repair.md`
		- `scene.places`와 `scene.llm_clip_prompt`를 보강하는 기준 추가.
- 이유
	- 흰 배경 clip 문제는 주로 structure 부족에서 비롯되므로, skill이 그 부족분을 메우는 쪽이 운영상 더 적합하기 때문.

[2026-03-11] Gemini clip 이미지 호출 timeout 추가

- 목적
	- 특정 clip 이미지 요청이 Gemini API에서 장시간 반환되지 않을 때 파이프라인 전체가 무기한 멈추는 문제를 막기 위함.
- 변경
	- `yadam/gen/gemini_client.py`
		- Gemini Flash Image `generate_content()` 호출을 daemon thread + 90초 timeout으로 감쌈.
		- timeout 시 `TimeoutError`를 발생시켜 기존 transient/error 처리 흐름으로 복귀하도록 변경.
- 이유
	- story14 clip 재생성 중 scene 033에서 장시간 블로킹되며 이후 scene들이 진행되지 않는 현상이 확인되었기 때문.

[2026-03-11] 시장 place prompt에 웹툰풍/군중 밀도 제한 추가

- 목적
	- `읍내 시장` 같은 market place 이미지가 다른 장소들보다 과도하게 반실사·과밀 군중 묘사로 치우치는 문제를 줄이기 위함.
- 변경
	- `yadam/prompts/builder.py`
		- `시장/장터/저잣거리/시장통` 키워드가 포함된 place prompt에 대해:
			- 군중 중간 밀도 유지
			- 배경 인물 단순화
			- 반실사 질감 억제
			- 한국 웹툰풍 선화/평면 색면 우선
			- 좌판/천막/항아리 등은 유지하되 과밀 구성 회피
		  규칙 추가.
- 이유
	- story14의 `place_004_읍내_시장.jpg`가 다른 place reference보다 화풍이 많이 달라, market 전용 스타일 고정이 필요했기 때문.

[2026-03-11] make_vrew skill에 place reference review + repair 단계 추가

- 목적
	- 7/8단계 뒤 place reference 자체의 의미/화풍 문제를 Codex가 보정하고, 필요 시 관련 clip까지 연쇄적으로 다시 묶을 수 있도록 workflow를 강화.
- 변경
	- `skills/make_vrew/SKILL.md`
		- character review 다음에 place review + repair 단계를 추가.
	- `skills/make_vrew/scripts/check_place_refs.py`
		- place image meta/path/status/stale error file를 검사하는 자동 점검 스크립트 추가.
	- `skills/make_vrew/references/place_ref_review.md`
		- place semantic/style drift, 불필요한 군중, dependent clip reset 기준을 정리.
- 이유
	- `산길` reference에 사람 행렬이 들어가 오누이 장면 전체가 어색해진 사례처럼, place 단계의 오류가 여러 clip에 전파될 수 있기 때문.
- 2026-03-11
  - `make_vrew` skill에 step 7/8 전 구조 sanity gate를 추가했다.
  - 새 스크립트 `skills/make_vrew/scripts/check_structure_ready.py`가 generic role canonical name, human/animal species mismatch, protagonist reference 부재, scene character coverage 부족을 검사한다.
  - `skills/make_vrew/SKILL.md`를 갱신해 `check_structure_ready.py` 통과 전에는 캐릭터/장소 reference 생성으로 진행하지 않도록 했다.
  - `skills/make_vrew/scripts/check_character_refs.py`도 강화해 generic canonical name, species mismatch, protagonist reference 부재를 hard blocker로 본다.
  - `story25` 같은 seed-quality character 구조(`나리/스님/아버지/아들`, `species=소`)가 있으면 이제 step 9 이전이 아니라 step 7/8 이전에 중단된다.
  - 추가로 `make_vrew` skill을 갱신해 구조 이상을 발견하면 단순 중단하지 않고 `references/structure_repair.md` 기준으로 `project.json` 구조를 먼저 수리한 뒤, `check_structure_ready.py`를 재실행하고 step 7/8로 진행하도록 했다.

[2026-03-11] 연속 장면 disguise continuity 강화

- 목적
	- 같은 인물/같은 variant가 연속 scene에 등장할 때 clip마다 복장과 머리장식이 바뀌는 문제를 줄이기 위함.
- 변경
	- `yadam/pipeline/orchestrator.py`
		- scene `variant` 문구를 복식/외형 앵커로 승격하는 `_augment_anchors_with_variant()` 추가.
		- clip continuity block에 “adjacent scenes with same character+variant must keep the exact same disguise/headwear/color family” 규칙 추가.
		- clip prompt용 `visual_anchors`, `wardrobe_anchors` 생성 시 variant 기반 disguise 앵커를 자동 주입.
	- `yadam/nlp/llm_scene_prompt.py`
		- 같은 인물과 같은 variant가 인접 장면에서 반복되면 같은 변장/복색/머리 계열을 유지하고 scene마다 새 의상으로 재해석하지 말라는 규칙 추가.
- 이유
	- story25의 scene `040~042`처럼 같은 `숯칠한 얼굴과 남루한 거지 변복` variant인데도 clip별로 옷/모자/색이 크게 바뀌는 drift가 확인되었기 때문.
[2026-03-15] make_vrew skill에 clip 생성 전 continuity gate 강화

- 목적
	- 다른 story에서도 이미지 생성 전에 drift 원인을 prompt/binding 단계에서 먼저 차단하도록 하기 위함.
- 변경
	- `skills/make_vrew/SKILL.md`
		- step 9 직전 점검 항목에 `scene_bindings` 과잠금, 아동 주인공 앵커 누락, 회복/복식 전환 상태 누락을 prompt-stage blocker로 추가.
	- `skills/make_vrew/references/clip_prompt_review.md`
		- broad binding으로 잘못된 인물이 연속 scene에 주입되는 경우를 생성 전 review priority로 추가.
		- 아동 체구/모자/복식 drift, 정체 공개 후 복식 전환 누락을 prompt review 단계에서 잡도록 보강.
	- `skills/make_vrew/references/clip_prompt_repair.md`
		- prompt만 늘리지 말고 `scene_bindings`/`scene.characters` 자체를 먼저 고치라는 repair 규칙 추가.
		- 소품 위 자연스러운 책/장부 글씨는 허용하되, 말풍선/효과음/캡션형 텍스트는 계속 금지하도록 기준을 명확화.
- 이유
	- `story27`에서 조익현이 broad binding 때문에 불필요한 연속 scene에 끼어들고, 이설/월화의 복식 상태가 후반부에서 되돌아가는 문제가 이미지 생성 전 prompt-stage에서 이미 보였기 때문.

[2026-03-16] story27 clip continuity 보정에서 확인된 운영 노하우 문서화

- 목적
	- 다음 세션에서 `story27` 같은 아동 주인공 continuity 붕괴와 scene-level 오독을 더 빨리 복구하기 위함.
- 변경
	- `AGENTS.md`
		- 아동 주인공 drift가 보이면 prompt에 체형/연령/머리장식/도포 색을 다시 잠그는 규칙 추가.
		- 동일 인물 중복 생성이 보이면 `exactly one boy/one guard/...`처럼 인원 수를 직접 잠그라는 규칙 추가.
		- 화상/관복/규수 복장처럼 상태 전환이 끝난 구간은 story-local YAML에도 함께 남기라는 규칙 추가.
		- `EMPTY_IMAGE_BYTES` 반복 scene은 더 짧고 덜 민감한 prompt로 scene 단위 재시도하라는 운영 메모 추가.
- 운영 메모
	- `story27`에서 실제로 효과가 있었던 보정 패턴:
		- 초반 궁 장면 `008~012`: “child-sized twelve-year-old boy”, `black headwrap`, `light cream scholar robe`를 같은 문장 구조로 반복해 초반 얼굴/복식 drift를 줄였다.
		- `033`: 대본상 예를 갖춘 꿇음이 아니라 바닥 단서를 줍기 위해 몸을 낮추는 장면이므로, 포즈보다 실제 행위를 기준으로 prompt를 고쳐야 했다.
		- `046, 048~051, 071, 074~076`: 월화/박 서방과 3인 장면은 `exactly one boy, one guard, and one shaman`이 중복 인물 억제에 유효했다.
		- `125~139`: 화재 이후 이설은 `smoke-stained cream robe`, `bandaged forearm` 같은 회복 전 상태를 prompt에 다시 적어야 후반부에서 복장이 초기화되지 않았다.
		- `137~141`: 후반 보상 구간은 `story27_variant_overrides.yaml`, `story27_scene_bindings.yaml`에 박 서방 관복/월화 규수 복장을 같이 남겨 두는 편이 다음 재실행 때 안전했다.
		- `111`: `EMPTY_IMAGE_BYTES`는 긴 액션 prompt보다 더 짧고 단순한 “burning prison entrance + one boy runs into flames toward trapped guard” 식 prompt로 낮추자 복구됐다.
- 이유
	- 이번 `story27` 보정에서 문제의 대부분이 모델 자체보다 prompt 앵커 부족, exact cast 미고정, 상태 전환 YAML 누락, scene 동작 해석 오류에서 나왔기 때문.
