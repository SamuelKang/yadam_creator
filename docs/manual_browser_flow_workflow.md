# 브라우저 Flow 수동 생성 워크플로우 (story17)

이 문서는 `story17`을 기준으로 Google Flow에서 clip 이미지를 수동/반자동으로 생성하기 위한 준비 절차다.

## 1) 파이프라인 준비 (character/place skip)

```bash
python -m yadam.cli --story-id story17 --browser-image-mode flow --through-clip-prompts --non-interactive
```

동작:
- scene 구조/프롬프트 준비 단계까지 진행
- character/place 레퍼런스 생성 단계는 skip
- clip prompt 준비 후 이미지 생성 전에 종료

## 1.5) 실행 전 프롬프트 점검 (권장)

브라우저 Flow 경로에서는 `scenes[].image.prompt_used`를 최종 입력으로 간주한다.
`llm_clip_prompt`는 압축 요약/검수용으로 유지한다.

점검 포인트:
- `scene.text` 기준 인물/장소 태깅이 맞는지 (`scenes[].characters`, `scenes[].places`)
- `prompt_used`가 템플릿 감정문이 아닌 장면 기반 동작을 담는지
- shot/인원수 모순이 없는지
- 집/마당/관아/산길 배경 오염이 없는지
- 길이 70~140 단어 범위인지

빠른 길이 점검:

```bash
python - <<'PY'
import json
d=json.load(open('work/story17/out/project.json'))
ws=[len((s.get('image',{}).get('prompt_used','')).split()) for s in d['scenes']]
print('min',min(ws),'max',max(ws),'avg',round(sum(ws)/len(ws),1))
print('lt70',sum(w<70 for w in ws),'gt140',sum(w>140 for w in ws))
PY
```

## 2) Flow 브라우저 자동화 실행 (CDP batch)

Chrome를 원격 디버깅으로 띄운 뒤:

```bash
python scripts/playwright_gemini_cdp_batch.py \
  --story-id story17 \
  --url https://labs.google/fx/tools/flow \
  --skip-character-precheck \
  --no-ensure-image-mode \
  --require-manual-confirm
```

권장:
- 먼저 `--start-scene 1 --end-scene 10` 소구간으로 테스트
- 성공 패턴 확인 후 범위를 넓혀 실행

## 3) 결과 파일

- 생성 이미지: `work/story17/clips/*.png`
- 실행 리포트: `work/story17/logs/gemini_batch_*.json`
- 프롬프트 소스(Flow 입력): `work/story17/out/project.json`의 `scenes[].image.prompt_used`
- 보조 요약 프롬프트: `work/story17/out/project.json`의 `scenes[].llm_clip_prompt`

## 4) 인물 일관성 팁

- Flow에서 인물 기준 이미지를 asset/ingredient로 넣을 수 있으면 반드시 고정 사용
- 장면 프롬프트마다 동일 인물 고정 문구(나이/체형/복식/머리)를 반복
- 인원 수는 `exactly one ...`처럼 수량 잠금

## 5) 현재 작업 상태 (2026-04-09, 중단 시점 기록)

이번 세션에서 `scripts/playwright_gemini_cdp_batch.py`에 아래 Flow 대응을 추가했다.

- Flow 랜딩 진입 단계 추가:
  - `+ 새 프로젝트` 클릭 시도
  - `Create with Flow` 클릭 시도
- Flow 생성 전 preflight 추가:
  - 모델/이미지-동영상/비율/출력 개수 컨트롤 감지
  - 기본 선택 시도: `Nano Banana 2`, `이미지`, `16:9`, `1개`
- 같은 host의 기존 탭을 재사용할 때 `goto`로 페이지를 재로딩하지 않도록 보강
- 제출 단계에서 `Enter` + `Generate/Create` 버튼 클릭 시도
- 저장 단계에서 download/src-fetch 실패 시 이미지 스크린샷 저장 폴백 추가

확인된 상태:

- `prompt_input_not_found` 단계는 해소됨
- 최근 중단 로그는 `timeout_no_image` / `save_failed_download` 유형이 확인됨
- 사용자 관찰 기준으로, 자동 실행 시 Flow 탭이 랜딩으로 돌아가는 케이스가 있어 수동 진입 직후 재시작이 필요함

다음 재개 시 권장 순서:

1. 브라우저에서 수동으로
   - `+ 새 프로젝트` 클릭
   - `Create with Flow` 클릭
   - 입력 박스/컨트롤 영역(모델/이미지·동영상/비율/출력개수) 노출 확인
2. 아래 소구간 테스트 실행
```bash
.venv/bin/python scripts/playwright_gemini_cdp_batch.py \
  --story-id story17 \
  --url https://labs.google/fx/tools/flow \
  --start-scene 1 \
  --end-scene 1 \
  --skip-character-precheck \
  --no-ensure-image-mode \
  --timeout-sec 180 \
  --state-debug
```
3. 성공 시 `--start-scene 1 --end-scene 3`으로 확장

검증 포인트:

- 로그: `work/story17/logs/gemini_batch_*.json`
- 산출물: `work/story17/clips/001.png` 생성 여부

## 6) 현재 작업 상태 (2026-04-10, story16 재개용 메모)

이번 세션에서 `scripts/playwright_gemini_cdp_batch.py`를 추가 보정했다.

- Flow 입력창 판정 보정:
  - `textarea` 첫 요소가 `g-recaptcha-response`인 경우를 제외하도록 수정
  - 실제 입력창(`contenteditable role=textbox`) 기준으로 입력 가능 여부 판정
- Flow 제출 버튼 보정:
  - `arrow_forward / 만들기` 버튼 우선 클릭
  - `Create with Flow`, `+ 새 프로젝트` 오탐 회피
- Flow 랜딩/컨트롤 보정:
  - `+ 새 프로젝트` 재시도
  - 하단 통합 컨트롤(`Nano Banana 2 | crop_16_9 | xN`) 탐지 보강
- 안정성 보정:
  - 네비게이션 중 `Execution context was destroyed` 예외 방어
  - 입력/제출 직전 `Esc`로 팝오버 닫기 시도

확인된 제약:

- 현재 계정/화면 기준으로 하단 통합 설정이 `x2`로 표시되며,
  자동화에서 `x1` 선택 노드를 DOM에서 안정적으로 찾지 못함.
- 즉, 프롬프트 1회 제출 시 결과가 2장 생성될 수 있음.
- `error_network`로 리포트가 남아도 실제 화면에는 이미지가 생성된 경우가 확인됨.

실제 확인 산출물:

- Flow 화면 캡처: `work/story16/clips_flow_test/flow_current_view.png`
- 화면에서 직접 캡처 저장: `work/story16/clips_flow_test/flow_scene001_manual_captured.jpg`
- 최근 리포트 예:
  - `work/story16/logs/gemini_batch_1775808595.json` (`error_network`)
  - `work/story16/logs/gemini_batch_1775807352.json` (`timeout_no_image`)

다음 세션 재개 절차 (story16):

1. Chrome CDP 단일 세션으로 시작
```bash
osascript -e 'tell application "Google Chrome" to quit'
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp-flow --new-window https://labs.google/fx/tools/flow
```
2. Flow 프로젝트 화면에서 하단 상태 확인
   - 기대값: `🍌 Nano Banana 2 | crop_16_9 | x2` (현재 제약)
3. 소구간 실행
```bash
.venv/bin/python scripts/playwright_gemini_cdp_batch.py \
  --story-id story16 \
  --url https://labs.google/fx/tools/flow \
  --start-scene 1 \
  --end-scene 1 \
  --skip-character-precheck \
  --timeout-sec 240 \
  --state-debug \
  --download-dir work/story16/clips_flow_test
```
4. 어둡게 생성되면 밝기 보정 suffix 적용
```bash
--prompt-suffix "bright natural daylight, readable midtones, avoid underexposure, preserve shadow detail, keep contrast balanced"
```
5. 자동 감지 실패 시 화면 직접 캡처로 구제
   - `flow_sceneXXX_manual_captured.jpg` 패턴으로 저장 후 후처리

## 7) 안정 운영 모드 (2026-04-11, story16 검증 완료)

현재까지 가장 안정적인 실행 모드는 아래와 같다.

- 단일 scene 완전 직렬 실행(`start-scene == end-scene`)
- 생성 중 폴링 1초
- 자동 재제출 비활성(기본): 한 scene당 submit 1회
- Flow 예외 UI(예: `Veo 3.1 Lite`, `시작하기`) 자동 닫기 선행

### 권장 실행 커맨드 (단건)

```bash
.venv/bin/python scripts/playwright_gemini_cdp_batch.py \
  --story-id story16 \
  --url https://labs.google/fx/tools/flow \
  --start-scene 2 \
  --end-scene 2 \
  --overwrite \
  --gen-poll-sec 1.0 \
  --start-fallback-sec 15 \
  --timeout-sec 240 \
  --cooldown-sec 2 \
  --idle-timeout-sec 90 \
  --idle-stable-sec 2.0 \
  --idle-poll-sec 0.5
```

### 상태 판정 규칙 (요약)

- 제출 직후 `running banner/stop/busy` 신호가 없어도,
  이미지 변화(`count/hash/src`)가 보이면 시작 상태로 인정.
- 시작 후 `idle` 복귀가 2회 이상 연속이고 이미지 변화가 확인되면 완료.
- `quota/blocked/network/stopped`는 오류 분기 유지.
- `network`는 일시 토스트 오탐을 줄이기 위해 짧은 유예 후 재판정.

### 빠른 생성(<15초) 대응

- 15초 이전이라도 이미지 변화 + idle 안정 조건을 만족하면 즉시 완료 판정.
- 즉, `start-fallback-sec=15`는 최소 대기 시간이 아니라,
  러닝 신호가 아예 없는 경우를 위한 보조 시작 판정 기준이다.

### 운영 수칙

1. 자동화 실행 중에는 사용자 마우스/키보드 입력을 하지 않는다.
2. scene 경계(완료/실패 리포트 출력)에서만 수동 개입한다.
3. 실패 시 다음 scene으로 넘어가지 말고 같은 scene에서 원인 확인 후 재시도한다.

### 원본 다운로드 실패 시 fallback

- 1차: Flow 다운로드 버튼 클릭
- 2차: `src` 직접 fetch
- 3차: 화면 캡처 저장

> 참고: 현재 보고 있는 이미지와 저장 파일이 어긋나는 경우가 있으므로,
> 크게보기 모달 상태에서 수동 다운로드 후 파일 반영 경로를 항상 대안으로 둔다.

## 8) 다음 세션 필수 인수사항 (2026-04-11 업데이트)

### A. 완료 판정 규칙 (중요)

- `count` 단독 증감으로 완료를 판정하지 않는다.
- 아래 중 하나라도 있으면 완료 금지:
  - `생성 중`, `로딩`, `진행 중`, `%` 진행률 텍스트
  - stop/busy 신호가 남아 있는 상태
- 배치 스크립트는 `--min-post-submit-sec 25`를 기본으로 사용한다.

### B. `"프롬프트를 입력해야 합니다"` 경고 대응

- 현재 Flow에서는 이 경고가 잔존/오탐처럼 보이는 경우가 있다.
- 경고가 보이더라도 자동 재입력-재생성 루프를 돌리지 않는다.
- 운영 정책:
  1. 해당 scene 자동 배치를 멈춘다.
  2. UI에서 `... -> 프롬프트 재사용`으로 실제 생성 프롬프트를 확인한다.
  3. scene 프롬프트와 일치하면 그 이미지를 저장한다.

### C. 저장 전 검증 우선순위

1. 마지막(좌상단) 카드의 `프롬프트 재사용` 텍스트가 scene 프롬프트와 일치하는지 확인
2. 일치 시에만 저장
3. 저장 후 직전 scene과 동일 이미지인지 해시/유사도 검사

### C-1. `프롬프트 재사용` 열기 정확 절차 (2026-04-11 검증)

- 최신 카드는 그리드의 **좌상단**으로 간주한다. (DOM 마지막 이미지 아님)
- 최신 카드 위에 마우스를 올리면 아이콘 3개가 나타난다.
  - 1번째: 하트(즐겨찾기)
  - 2번째: 회전 화살표(빠른 재사용)
  - 3번째: 점 3개(더보기)
- 운영 기준:
  1. **3번째 점 3개 아이콘** 클릭
  2. 메뉴에서 `프롬프트 재사용` 클릭
  3. 입력창에 채워진 텍스트가 대상 scene 프롬프트와 **exact match**인지 확인
  4. exact match일 때만 해당 카드 이미지를 `work/<story-id>/clips/NNN.png`로 저장

- `error_prompt_required` 토스트가 보여도, 위 exact match가 성립하면 저장 가능으로 본다.
- 입력창이 긴 토큰 문자열(reCAPTCHA 등)로 보이면 프롬프트가 아닌 것으로 간주하고 저장하지 않는다.

### D. 탭/프로브 주의사항

- 상태 프로브는 반드시 Flow 탭(`/tools/flow`)을 기준으로 읽는다.
- `gemini.google.com/app` 탭 값이 섞이면 count/상태가 틀어질 수 있다.

### E. story16 실무 운영 방식

- 자동 생성은 단건(scene 1개) 위주로 실행
- 자동 저장 실패 시:
  - 재생성보다 `이미 생성된 카드`를 프롬프트 대조 후 수동 반영 우선
- 실제 반영 파일은 `work/story16/clips/NNN.<원본확장자>`로 저장
