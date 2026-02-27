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
