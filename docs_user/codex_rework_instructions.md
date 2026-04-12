# Codex 재작업 지시서

기준 파일: `project.json`

현재 버전은 이전보다 개선되었지만, 아직 아래 문제가 남아 있다.  
특히 `scene` 레벨은 지브리 방향으로 좋아졌으나, `character/place` 레벨은 여전히 웹툰 스타일 잔재가 있고, 일부 scene은 대본보다 `places` 메타를 과하게 따른다. fileciteturn4file0

## 현재 상태 요약

### 잘 된 점
- `project.style_profile`이 `ghibli_hand_drawn_2d`로 바뀌어 전역 스타일 충돌이 크게 줄었다. fileciteturn4file0
- 많은 scene에서 `llm_clip_prompt`와 `image.prompt_used`가 동기화되었다. fileciteturn4file0
- 초반 scene의 `night / village courtyard / hungry villagers` 반복 템플릿이 줄고, 서리·들판·곡간 폐허·냉랭한 낮빛 등 대본 기반 요소가 많이 반영되었다. fileciteturn4file0

### 남은 문제
- `characters[*].image.prompt_used`와 `places[*].image.prompt_used`에 아직 `한국 웹툰 스타일` 문구가 남아 있다. fileciteturn4file0
- 일부 scene은 대본보다 `places` 메타를 너무 기계적으로 따라간다. 예: scene 8~9가 논/밭의 괭이질 문맥인데 `burned granary ruins` 쪽으로 기운다. fileciteturn4file0
- 일부 scene은 실내/실외 판단이 어긋난다. 예: scene 6은 초가집 외부와 마당 긴장인데 실내/툇마루 중심으로 기운다. fileciteturn4file0
- 추상적 문장(`Characters hold tense stances...`)이 남아 있어 화면 지시가 덜 구체적이다. fileciteturn4file0

---

## 이번 작업 목표

1. `scene` 프롬프트의 문맥 정확도를 높인다.  
2. `character/place` 프롬프트의 화풍도 지브리 방향으로 통일한다.  
3. `places` 메타를 참고하되, **대본 본문(scene.text)**을 최우선 기준으로 삼는다.  
4. 추상적 문장을 줄이고, **화면에 실제로 보이는 행동/표정/배치** 중심으로 다시 쓴다.

---

## 강제 규칙

### 규칙 1. 대본 우선
- `scene.text`를 최우선으로 해석하라.
- `places`와 `characters`는 보조 제약이다.
- `places` 목록에 있다고 해서 무조건 그 장소를 대표 배경으로 쓰지 말고, 해당 장면 문장에 실제로 드러나는 공간을 먼저 선택하라.

예:
- 판수가 마른 논에 괭이를 내리치는 장면이면 `field / cracked soil / paddies` 우선
- 곡간이 배경 서사로만 연결되어 있어도, 화면 행동이 들판이면 곡간 폐허를 전면 배경으로 쓰지 말 것

### 규칙 2. 실내/실외 정확화
- 대문, 마당, 바람, 서리, 울타리 → 실외
- 초가집 안, 종이문, 실내 어둠, 기름등 → 실내
- 툇마루는 실내가 아니라 반외부 공간으로 처리

### 규칙 3. 화풍 통일
다음 계층 모두 지브리 방향으로 맞출 것:
- `project.style_profile`
- `scenes[*].llm_clip_prompt`
- `scenes[*].image.prompt_used`
- `characters[*].image.prompt_used`
- `places[*].image.prompt_used`

다음 계열 문구는 current prompt에서 제거:
- `한국 웹툰 스타일`
- `Korean webtoon`
- `Korean manhwa/webtoon look`
- `정돈된 캐릭터 디자인풍(B군)` 같은 웹툰 중심 문맥

대신 아래 방향으로 통일:
- `Ghibli-inspired hand-drawn 2D animation`
- `painterly backgrounds`
- `soft natural lighting`
- `expressive but grounded acting`
- `no visible text, subtitles, or speech bubbles`

### 규칙 4. 추상 문장 금지
다음 같은 문장은 피할 것:
- `Characters hold tense stances...`
- `react through eye-line, posture, and hand movement`
- `restrained tension`만 단독 사용

대신 실제로 보이는 장면으로 쓸 것:
- 판수가 괭이를 치켜든다
- 수련이 이를 악물고 정면을 노려본다
- 포교가 밧줄과 몽둥이를 든 채 들이닥친다
- 최 씨가 뒤에서 냉소적인 눈빛으로 지켜본다

### 규칙 5. shot type과 내용 일치
- `wide shot`: 공간과 인물 배치 함께
- `medium shot`: 상반신~무릎 중심의 행동
- `close-up`: 얼굴, 손, 눈빛, 입술, 손등 등 세부 묘사
- `tracking shot`: 이동 감각이 실제로 필요할 때만
- `high-angle`/`low-angle`: 감정 의도가 명확할 때만

### 규칙 6. 무인 환경샷 문구 남용 금지
- `No central character appears in frame`는 꼭 필요한 정경샷에만 사용
- scene에 주민/아이/행인이 실제로 보이면, 그 사실을 직접 쓰고 “무인 샷”처럼 보이게 하지 말 것

---

## 우선 재수정 대상 scene

### 1차 우선 수정
- **scene 6**
  - 현재 문제: 초가집 외부의 불길한 긴장인데 실내/툇마루 중심으로 기운다
  - 수정 방향: 초가집 외관, 서리 맞은 마당, 흔들리는 대문, 바람이 핵심

- **scene 8~9**
  - 현재 문제: 판수의 괭이질 장면인데 곡간 폐허 배경으로 과도하게 치우침
  - 수정 방향: 마른 논/갈라진 흙/들판 또는 마을 외곽 농토 중심으로 재작성

- **scene 7**
  - 현재 문제: 인물 소개 장면인데 추상 문장이 남아 있음
  - 수정 방향: 굽은 등, 무너진 울타리 너머, 갈라진 손등, 판수의 체구를 화면적으로 더 구체화

### 2차 우선 수정
- **scene 1~5**
  - 지금은 전보다 좋아졌지만 `No central character appears in frame` 반복이 기계적임
  - 장면별 차이를 더 선명히 분화
  - scene 2는 주민과 아이들이 실제로 보여야 함

### 3차 우선 수정
- **scene 14~22, 54~61, 80~88, 102~134**
  - 대인 갈등이 본격화되는 구간
  - 각 장면에서 누가 중심 인물인지, 갈등 축이 누구인지 더 분명히 드러내기
  - 수련/최 씨/포교/관복 위장 변형의 시각 차이를 강화

---

## character / place 프롬프트 재정비 규칙

### character 프롬프트
다음 필드 current prompt에서 웹툰 중심 문구 제거:
- `화풍: 한국 웹툰 기반`
- `정돈된 캐릭터 디자인풍(B군)`
- `균일한 2D 셀 셰이딩`
- 기타 웹툰 스타일 고정 표현

대체 방향:
- 조선 시대 복식·신분·표정 정보는 유지
- 화풍은 지브리풍 손그림 2D 애니메이션 쪽으로 정리
- 질감은 너무 깨끗한 웹툰 캐릭터 카드가 아니라, 배경과 어울리는 부드러운 채색과 자연스러운 손그림 질감으로 정리

### place 프롬프트
현재 place 프롬프트도 `한국 웹툰 스타일` 문구가 남아 있다. 이를 다음 방향으로 변경:
- `Ghibli-inspired hand-drawn 2D background`
- `painterly environmental detail`
- `soft natural light`
- `no visible text`

장소별로 시간대 앵커도 재검토:
- `place_003`의 `cold night wind`
- `place_004`의 `torch-lit`
- `place_006`의 `moonlit mist`

이런 표현은 대본에 밤이 없으면 기본 배경 기준으로는 과하다.  
장소 기본 앵커는 **시간 중립적** 또는 **낮 기준**으로 조정하고, 실제 야간은 scene 레벨에서만 활성화할 것. fileciteturn4file0

---

## 출력 규칙

- JSON 구조는 유지한다.
- 다음 필드를 우선 수정한다:
  - `project.style_profile`
  - `scenes[*].llm_clip_prompt`
  - `scenes[*].image.prompt_used`
  - `characters[*].image.prompt_used`
  - `places[*].image.prompt_used`
- `prompt_history`는 삭제하지 말고 과거 기록으로 남긴다.
- 현재값(current prompt)은 최신 기준으로 정리한다.
- 불필요한 영어 추상문 반복을 줄이고, 장면별로 서로 다른 이미지가 나올 수 있게 구체성을 확보한다.

---

## 재작성 예시 원칙

나쁜 예:
- `Characters hold tense stances and react through eye-line, posture, and hand movement.`
- `No central character appears in frame.`를 반복적으로 삽입
- `burned granary ruins`를 대본과 무관하게 place 목록 때문에 고정 사용

좋은 예:
- `Pansu stands beyond a broken fence, his back bent and his cracked hands gripping the hoe handle.`
- `The frost-covered yard lies empty except for the gate shaking in the wind.`
- `Starving villagers crouch beside the roadside while children cling to doorways.`
- `Suryeon faces the intruding officers with her jaw set and sleeves pulled tight.`

---

## Codex에게 최종 작업 명령

```text
project.json을 다시 수정하라.

목표:
1) scene.text를 최우선 기준으로 scene 프롬프트 문맥 정확도를 높인다.
2) scene / character / place 프롬프트의 화풍을 모두 Ghibli-inspired hand-drawn 2D animation 방향으로 통일한다.
3) places 메타를 보조 제약으로만 사용하고, 대본 행동과 공간이 충돌하면 대본을 우선한다.
4) 추상 문장을 줄이고 실제 화면에 보이는 행동, 표정, 배경 요소 중심으로 다시 쓴다.

반드시 수정할 것:
- project.style_profile
- scenes[*].llm_clip_prompt
- scenes[*].image.prompt_used
- characters[*].image.prompt_used
- places[*].image.prompt_used

강제 규칙:
- night / moonlit / torch-lit는 대본에 야간이 없으면 current prompt에서 기본 사용 금지
- Korean webtoon / manhwa / B군 / 균일한 2D 셀 셰이딩 같은 웹툰 중심 문구 제거
- Ghibli-inspired hand-drawn 2D animation, painterly backgrounds, soft natural lighting 방향으로 통일
- scene 6, 7, 8, 9를 1차 우선 재작성
- scene 1~5는 No central character appears in frame 남용을 줄이고 장면별 차이를 강화
- scene 14~22, 54~61, 80~88, 102~134는 갈등축 인물과 행동을 더 분명히 재작성

출력 조건:
- JSON 구조 유지
- prompt_history 유지
- current prompt만 최신 기준으로 정리
```
