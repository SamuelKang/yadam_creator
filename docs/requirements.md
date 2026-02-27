작성일: 2026-02-24 (갱신: 2026-02-26)
범위: 조선시대 야담(기본) + 현대 시니어 사연(확장)
목표: 대본(.txt) → 장면(JSON) → 캐릭터/장소/장면 이미지 → 편집용 산출물

⸻

0. 핵심 목표
	1.	입력 대본(.txt)에서 장면을 분할하고(JSON)
	2.	등장인물/장소를 정리하며(일관성 유지)
	3.	캐릭터/장소 이미지와 장면(clip) 이미지를 생성하고
	4.	결과를 스토리 단위 폴더에 정리한다.

파이프라인은 중간 에러가 발생해도 전체 흐름을 중단하지 않고, 재실행 시 실패한 항목만 재시도할 수 있어야 한다.

⸻

1. 입력 규칙
	•	입력은 story_id로 받는다. 예: story00
	•	입력 대본 파일:
	•	stories/{story_id}.txt

⸻

2. 출력 규칙(스토리 단위 디렉토리)
	•	결과물 출력 루트:
	•	work/{story_id}/
	•	하위 디렉토리:
	•	work/{story_id}/characters/ : 인물 이미지(카탈로그)
	•	work/{story_id}/places/     : 장소 이미지(카탈로그)
	•	work/{story_id}/clips/      : 장면 이미지(clip)
	•	work/{story_id}/out/        : project.json, vrew payload 등
	•	work/{story_id}/logs/       : 로그

⸻

3. 단계별 요구사항(1~7)

3.1 대본 입력
	1.	stories/{story_id}.txt를 읽는다.

3.2 인물 추출/정리/이미지 생성
	2.	대본을 분석해 등장인물(주인공/조연)을 정리한다.

	•	LLM 기반 정규화(권장): 별칭 병합, 대표명(name_canonical) 확정, 특징/외형 앵커(visual_anchors) 생성.
	•	인물 카탈로그 이미지를 생성해 characters/에 저장한다.

캐릭터 이미지 생성 규격
	•	이미지 비율: 3:4
	•	캐릭터 프롬프트는 캐릭터 전용 스타일 프로필을 사용한다.
	•	이유: 기본 스타일(k_webtoon)의 suffix에 16:9가 포함되어 캐릭터 생성에도 16:9 지시가 섞이는 문제 방지.
	•	캐릭터용 스타일 프로필(예: k_webtoon_char)은 16:9 문구를 포함하지 않아야 한다.

아동 연령 기준(고정)
	•	캐릭터/장면 모두에서 “아동”의 기본 나이는 5세로 한다.
	•	variant 또는 age_stage가 “아동”인 경우, 프롬프트 입력의 age_hint는 “약 5세”로 정규화한다.
	•	아동 장면에서는 visual_anchors/wardrobe_anchors에서 청년/성인 단서를 제거해 외형 일관성을 유지한다.

3.3 장소 추출/정리/이미지 생성
	3.	대본을 분석해 주요 장소를 정리한다.

	•	LLM 기반 정규화(권장): 장소명 통합, 분위기/시간/구조 앵커(visual_anchors) 생성.
	•	장소 카탈로그 이미지를 생성해 places/에 저장한다.

3.4 장면 분할 JSON 생성
	4.	대본을 빈 줄 제외 후 의미 기준 3~5문장 단위 장면으로 분할해 JSON에 저장한다.

	•	scene.text는 해당 장면의 문장들을 합친 문자열이다.
	•	공백/개행/문장경계가 원문과 달라져도 무방하다.
	•	clip 파일명(예: 003.jpg)과 scene id(3)는 1:1 매핑된다.

3.5 장면별 인물/장소 태깅
	5.	장면별 등장 인물/장소를 JSON에 기록한다.

	•	LLM이 생성한 scene_tags를 우선 반영한다(별칭/대명사 처리 목적).
	•	실패 시 규칙 기반 태깅으로 폴백한다.

3.6 장면 이미지 생성 및 JSON 경로 기록
	6.	장면 단위로 이미지를 생성해 clips/에 저장하고, JSON에 이미지 경로 및 상태를 기록한다.

	•	장면 프롬프트에는 “말풍선/자막/캡션/패널/내레이션 박스/텍스트 박스 금지”를 명시한다.
	•	웹툰 스타일은 텍스트(말풍선/자막) 생성 확률이 높으므로 clip 전용 스타일 프로필(k_webtoon_clip)을 사용 가능해야 한다.
	•	clip LLM 입력 인물 정보에는 social_class뿐 아니라 wealth_level도 포함해 복식/분위기 일관성을 강화한다.
	•	clip 최종 프롬프트에는 character continuity lock 블록을 포함해 같은 인물의 외형/복식 핵심 앵커를 장면 간 유지한다.

clip 이미지 생성 규격
	•	이미지 비율: 16:9
	•	clip은 k_webtoon_clip 등 clip 전용 스타일을 사용 가능해야 한다.

3.7 편집용 산출물
	7.	.vrew 파일을 직접 생성해 out/에 저장한다.
	•	호환/디버깅 용도로 vrew_payload.json도 함께 생성할 수 있다.

⸻

4. 에러 처리(중단 금지) 및 재시도

4.1 공통 원칙
	•	이미지 생성/LLM 호출 실패 시에도 파이프라인은 중단하지 않는다.
	•	실패한 항목은 에러 파일과 JSON 상태를 남긴다.
	•	재실행 시 status=ok는 스킵, error/pending만 재시도한다.

4.2 에러 파일 규칙
	•	캐릭터: characters/char_001_이름_error.jpg
	•	장소: places/place_001_장소_error.jpg
	•	장면: clips/006_error.jpg
	•	성공 시 _error 파일은 삭제하고 정상 파일로 대체한다.

4.3 JSON 상태 필드(최소)
	•	status: ok | error | pending
	•	attempts
	•	last_error
	•	path
	•	policy_rewrite_level (정책 차단 완화 단계)
	•	디버깅: prompt_original, prompt_used, prompt_history

⸻

5. 정책 차단 및 프롬프트 완화(리라이트)
	•	정책 차단(필터) 판단 시 프롬프트를 단계적으로 완화하여 재시도한다.
	•	완화 레벨을 JSON에 기록한다.

⸻

6. 화풍/시대 프로필(설정)
	•	era_profile: 조선 야담/현대 사연 등
	•	style_profile: 기본 화풍
	•	k_webtoon_clip: clip 전용(말풍선/자막/패널/내레이션 박스/텍스트 박스 강력 금지)
	•	k_webtoon_char: 캐릭터 전용(캐릭터는 3:4이므로 suffix에 16:9 금지)

⸻

7. LLM 기반 추출(권장)
	•	인물/장소/장면태깅은 규칙 기반 후보(seed) + LLM 정규화를 결합한다.
	•	clip 장면 프롬프트 LLM 입력에는 era_profile 이름만이 아니라 era prefix(예: “배경: 조선시대...”)를 함께 전달해 시대 배경을 명시한다.
	•	Gemini Developer API 호환을 위해 scene prompt structured output schema는 additionalProperties 없는 명시 필드 구조를 사용한다.
	•	LLM 결과:
	•	characters: name_canonical, aliases, role, traits, visual_anchors, gender, age_stage, age_hint, variants 등
	•	places: name_canonical, aliases, visual_anchors
	•	scene_tags: 장면별 인물/장소 연결(필요 시 character_instances 포함)

LLM 호출 진행상황 표시(heartbeat)
	•	LLM 호출이 길어지는 구간(예: entity extract)에서 사용자가 멈춘 것으로 오해하지 않도록,
	•	일정 주기(예: 1초)로 .을 출력하고,
	•	60초마다 줄바꿈과 함께 “still running…”을 출력한다.

⸻

8. CLI 운용 규칙(중요)

8.1 --non-interactive
	•	기본은 단계별 확인(대화형).
	•	--non-interactive 사용 시,
	•	파이프라인 내부 confirm들은 자동 진행한다.
	•	기존 산출물이 있으면 resume/재시도 중심으로 진행한다(기존 ok는 스킵, 실패만 재시도).

8.2 --clean-workdir
	•	실행 전에 work/{story_id}/만 대상으로 삭제할 수 있다(안전 체크 필수).
	•	사용 시 동작:
	•	항상 사용자에게 y/n 확인을 받는다.
	•	확인 입력은 반드시 y 또는 n만 유효하며, 엔터/기타 입력은 무효(재질문).
	•	사용자가 y를 선택하면 삭제 후 처음부터 진행한다.
	•	사용자가 n을 선택하면 삭제하지 않고 진행한다(resume).
	•	--clean-workdir는 work 하위 디렉토리에 대해서만 유효해야 한다(경로 탈출 금지).

8.3 --non-interactive + --clean-workdir
	•	--clean-workdir가 우선 동작한다.
	•	이 경우에도 --clean-workdir 확인은 반드시 y/n을 입력받는다.
	•	y 선택: 삭제 후 비대화형으로 끝까지 진행
	•	n 선택: 삭제하지 않고 비대화형으로 끝까지 진행

8.4 이미지 API 선택
	•	CLI에서 이미지 생성 백엔드를 선택할 수 있어야 한다.
	•	--image-api vertex_imagen | gemini_flash_image | comfyui
	•	--image-model 로 모델명을 오버라이드할 수 있어야 한다.
	•	기본값:
	•	vertex_imagen -> imagen-4.0-generate-001
	•	gemini_flash_image -> gemini-2.5-flash-image
	•	comfyui -> sd_xl_base_1.0.safetensors
	•	comfyui 사용 시:
	•	--comfy-url 로 서버 주소를 지정할 수 있어야 한다(기본 http://127.0.0.1:8188).
	•	--comfy-workflow 또는 COMFYUI_WORKFLOW_PATH 로 API workflow JSON 경로를 지정할 수 있다.
	•	둘 다 미지정이면 프로젝트 기본 템플릿(yadam/config/comfy_workflows/yadam_api_sdxl_base_fast_placeholders.json)을 사용한다.
	•	workflow JSON은 __PROMPT__/__NEGATIVE_PROMPT__/__WIDTH__/__HEIGHT__/__SEED__/__MODEL__ placeholder 치환을 지원해야 한다.
	•	운영 권장:
	•	실전 품질 일관성 기준의 기본 경로는 vertex_imagen으로 둔다.
	•	comfyui는 속도/비용/로컬 실행 실험용 보조 경로로 운용한다.

8.5 .vrew clip 자막 분할 옵션
	•	CLI에서 .vrew clip 분할 글자 수를 지정할 수 있어야 한다.
	•	--vrew-clip-max-chars <int> (기본 30)
	•	장면(scene.text)은 의미 단락(문장 경계 우선) 기준으로 분할하되, 분할 단위가 길면 글자 수 기준으로 추가 분할한다.

⸻

9. 운영 편의/출력 정책

폴더 자동 열기 비활성화
	•	실행 중 Finder 등으로 폴더를 자동으로 여는 동작은 모두 비활성화(코멘트 처리) 한다.
	•	이유: work/characters 등 폴더 창이 연속으로 열려 작업 흐름을 방해함.

ETA 표기
	•	ETA~는 “이미 지난 시간”이 아니라, 남은 예상 시간(Estimated Time Remaining) 으로 계산한다.
	•	계산 기준은 현재까지의 평균 처리 시간(평균 생성 소요)을 기반으로 한다.
	•	clip 진행 로그에는 elapsed~를 함께 출력해, [6/7] clips 시작 시점부터의 누적 경과 시간을 표시한다.

⸻

10. .vrew 직접 생성(신규)

목표
	•	모든 clip 생성 완료 후, project.json + clip 이미지 + scene 텍스트를 사용해 .vrew 파일을 직접 생성한다.

입력/출력
	•	입력:
	•	work/{story_id}/out/project.json
	•	work/{story_id}/clips/{scene_id:03d}.jpg
	•	출력:
	•	work/{story_id}/out/{story_id}.vrew

생성 조건
	•	scene별 image.status가 모두 ok일 때만 .vrew 생성을 진행한다.
	•	누락/실패 clip이 있으면 .vrew 생성은 실패 처리하고 오류 리포트를 남긴다.

매핑 규칙
	•	scene 순서는 project.json의 scene id 오름차순을 따른다.
	•	scene별 자막 텍스트는 project.json의 scene.text를 그대로 사용한다.
	•	scene.text는 .vrew clip으로 분할될 수 있으며(기본 30자), 분할된 하위 clip들은 모두 동일 scene 이미지를 공유한다.
	•	scene별 이미지는 clips/{id:03d}.jpg를 사용한다.
	•	scene별 voice는 Vrew 내부에서 추후 교체 가능한 dummy voice로 지정한다.
	•	scene duration은 자동 확정하지 않고, .vrew 생성 이후 Vrew 편집 과정에서 수동 조정한다.
