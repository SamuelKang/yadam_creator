# Story27 대본-이미지 정합성 점검 메모 (2026-03-16 KST)

목표: 사용자가 이미지를 직접 볼 수 없는 상황에서 story27 clip 이미지가 대본과 일치하는지 점검.

## 확인 범위
- 대본: `stories/story27.txt`
- 구조: `work/story27/out/project.json` (scenes 001-148)
- 이미지 시트:
  - `work/story27/out/story27_clips_001_013_sheet.jpg`
  - `work/story27/out/story27_clips_008_022_sheet.jpg`
  - `work/story27/out/story27_clips_023_030_sheet.jpg` (세션에서 생성)
  - `work/story27/out/story27_clips_031_037_sheet.jpg`
  - `work/story27/out/story27_clips_031_056_sheet.jpg`
  - `work/story27/out/story27_clips_031_060_sheet.jpg`
  - `work/story27/out/story27_clips_056_084_sheet.jpg`
  - `work/story27/out/story27_clips_070_097_sheet.jpg`
  - `work/story27/out/story27_clips_091_120_sheet.jpg`
  - `work/story27/out/story27_clips_098_115_sheet.jpg`
  - `work/story27/out/story27_clips_116_127_sheet.jpg`
  - `work/story27/out/story27_clips_121_148_sheet.jpg`

## 명확한 불일치(우선 수정 후보)
- 024-030: 서당 내부/아이들 수군거림/야간 관아 잠입/매화나무/습한 흙 → 이미지가 낮 시간 관아 마당/서당 정경 위주로 치환됨.
- 032: 세곡 습격 현장 설명인데 이미지가 책/손 클로즈업으로 불일치.
- 039-040: 사또 생신 잔치/시 낭송 장면인데 이미지가 관아 마당 서 있는 장면으로 치환됨.
- 042: 창고 잠입/인장 조각 회수 장면이 관아 마당 장면으로 치환됨.
- 057-060: 화살 빗속 탈출/동굴 은신/야간 결의 장면인데 낮 시간 길 위 정적 이미지로 치환됨.
- 061-062: 험준 산봉우리/바위틈 볏짚 단서 장면인데 대나무 숲 길 이미지로 치환됨.
- 077-081: 포졸 매복/박 서방 체포 장면이 단순 대나무 숲 동행 이미지로 약화됨.
- 082-084: 비바람 속 결의/고독 장면이 지하 감옥 복도 이미지로 치환됨.
- 085-090: 비 오는 밤 담 넘기/매화나무 아래 장부 발굴/사또 대면 장면이 낮 시간 관아 마당 이미지로 치환됨.
- 091-097: 비 속 포위/결의 독백 장면이 낮 시간 관아 마당 이미지로 치환됨.
- 106-107: 사또의 방화 명령/불길 확산 장면이 관아 마당 정지 장면으로 치환됨.
- 120: 화염 직후 결의 장면인데 낮 시간 대면 장면으로 치환됨.
- 126: 장부 투척/정면 선포 장면이 흰 배경의 인물 컷으로 불일치.
- 142-145: 세곡 재분배/아이들 눈물/고을 회상 장면이 시골길 이동 장면으로 치환됨.

## 부분 일치/주의 (맥락 약화 가능)
- 070-076: 동굴 이후 월화 등장/회상 장면이 대나무 숲 야간 대화로 처리됨.
- 098-105: 도깨비 정체(붉은 눈 아이들) 장면은 일부 반영되나, ‘붉은 눈/도깨비 분장’ 요소가 약함.
- 121-125: 관아 최종 대면은 불길/연기 대비가 약하고, 낮 시간 느낌으로 치환됨.

## 다음 액션(다음 세션용)
1. 위 불일치 장면들의 `scenes[].llm_clip_prompt`를 점검하고, 대본 핵심 요소(시간대/장소/행동) 반영되도록 수정.
2. 수정 대상 scene만 `pending`으로 되돌린 뒤 해당 구간 재생성.
3. 재생성 후 contact sheet로 재검수.


## 2026-03-16 추가 진행
- 불일치 장면들의 `llm_clip_prompt` 대대적 수정 및 재생성 완료.
- EMPTY_IMAGE_BYTES 재시도 대상: 032/057/120 → 프롬프트 단순화 후 재생성 완료(현재 status ok).
- 잔존 mismatch로 보였던 057(소년이 들쳐짐) → "boy runs on his own feet"로 수정 후 재생성 완료.

## 최신 정합성 점검(요약)
- 확인 시트: 
  - `work/story27/out/story27_clips_024_030_sheet.jpg`
  - `work/story27/out/story27_clips_031_042_sheet.jpg`
  - `work/story27/out/story27_clips_057_062_sheet.jpg`
  - `work/story27/out/story27_clips_077_084_sheet.jpg`
  - `work/story27/out/story27_clips_085_097_sheet.jpg`
  - `work/story27/out/story27_clips_106_107_sheet.jpg`
  - `work/story27/out/story27_clips_118_126_sheet.jpg`
  - `work/story27/out/story27_clips_142_145_sheet.jpg`
- 위 구간에서 대본-이미지 큰 불일치 없음. (밤/비/불/행동 요소 대부분 반영됨)

## 남은 할 일(선택)
- 더 엄격 검수(예: 092의 낮 광량/120의 화상 디테일 등)를 원하면 해당 scene만 재수정 가능.
- 최종 export까지 진행하려면 `run_through_clips.sh` 이후 export 단계 수행.

## 2026-03-16 현재 상태(세션 종료 직전)
- story27 clip 재생성 완료, `EMPTY_IMAGE_BYTES` 전부 해소.
- 주요 불일치 구간 재검수 완료(시트 목록은 위에 기록).

## 아직 전체 미검수 구간(추가 육안 확인 필요)
- 043-056
- 063-076
- 098-105
- 108-117
- 127-141
- 146-148

## 다음 세션 시작 지점
1) 위 미검수 구간을 contact sheet로 생성 후 대본-이미지 정합성 확인
2) 불일치 발견 시 해당 scene만 프롬프트 수정 → `pending` → 재생성
3) 전체 클립 정합성 완료 후 export 진행 여부 결정

## 2026-03-16 진행 재개 메모
- 사용자 요청: 미검수 구간(043-056, 063-076, 098-105, 108-117, 127-141, 146-148) 이어서 검수 진행.
- 다음 액션: 해당 구간 contact sheet 생성 후 대본 대비 이미지 점검, 불일치 발견 시 scene 단위로 prompt 수정/재생성.

## 2026-03-16 추가 수정 및 재검수
- scene 052: 화살 꽂힘/서당 내부 반영되도록 프롬프트 수정 → 재생성 완료.
- scene 098-100: 붉은 눈/붉은 가루 분장 요소 강화 → 재생성 완료.
- scene 134: 월화의 깊은 절(무릎 꿇고 조문) 반영 → 재생성 완료.
- 재생성 후 시트 확인:
  - `work/story27/out/story27_clips_043_056_sheet.jpg`
  - `work/story27/out/story27_clips_098_105_sheet.jpg`
  - `work/story27/out/story27_clips_127_141_sheet.jpg`
- 전체 미검수 구간 포함하여 전 범위 육안 검수 완료.
- `show_image_errors.py --include-clips` 결과: 에러 없음.
