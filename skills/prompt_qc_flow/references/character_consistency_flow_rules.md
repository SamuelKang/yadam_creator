# Character Consistency Rules (Flow)

## 목적
Google Flow용 이미지 프롬프트 검수/보정 시 씬 간 인물 일관성을 강하게 고정한다.

## 핵심 규칙

1. 캐릭터 고정 블록 강제 삽입
- 동일 문자열 유지
- 요약/변형/생략/순서 변경 금지

고정 블록:
`Main character: Korean male, early 40s, lean face, sharp cheekbones, narrow tired eyes, slightly tanned skin, thin mustache and short beard, traditional Joseon-era topknot (sangtu), worn brown hanbok with patched sleeves and rope belt, serious and restrained expression`

2. 프롬프트 구조 표준화
- `[STYLE BLOCK]`
- `[CHARACTER FIXED BLOCK]`
- `[SCENE DESCRIPTION + ACTION + EMOTION + CAMERA]`

고정 STYLE BLOCK:
`Ghibli-inspired hand-drawn 2D animation, painterly illustrated look, non-photorealistic rendering`

3. 캐릭터 표현 변경 금지
- 나이/얼굴 구조/눈/피부톤/상투/수염/기본 의상 고정
- 감정/자세/행동만 변경 가능

4. 의상 고정
- `worn brown hanbok with patched sleeves and rope belt`
- 색상/종류/장식 변경 금지

5. 부정 프롬프트 고정
`no modern hairstyle, no k-pop style, no japanese anime style, no text, no watermark, no extra characters, no different face`

6. 클로즈업 보정
- 연속 프롬프트 3~4개마다 최소 1개 close-up 자동 삽입

7. 인물 누락 방지
- 배경-only 프롬프트면 캐릭터 블록 + 행동 추가

8. 다중 인물 제한
- 기본 단일 주인공 유지
- 불필요한 군중 표현 제거

9. 고유명사 제거
- 지역/역사 인물/내부 설정 고유명사 제거 후 일반화

10. 표현 강도 보정
- 필요 시 `same character`, `consistent appearance` 삽입

## 출력 규칙
- 수정된 프롬프트만 출력
- 설명/주석 금지
- 독립 완결형 유지
- 줄바꿈 구조 유지
