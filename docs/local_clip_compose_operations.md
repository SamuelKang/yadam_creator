# Local Clip 합성 운영 문서

## 1) 목적
- `--compose-clips-from-refs` 모드에서 clip 이미지를 **원격 생성 없이 로컬 합성**으로 안정적으로 생성한다.
- 인물/장소 레퍼런스를 재사용해 비용과 생성 변동성을 줄인다.

## 2) 표준 실행 명령
```bash
python -m yadam.cli \
  --story-id <story-id> \
  --through-clips \
  --non-interactive \
  --compose-clips-from-refs \
  --image-api gemini_flash_image
```

예시:
```bash
python -m yadam.cli --story-id story15 --through-clips --non-interactive --compose-clips-from-refs --image-api gemini_flash_image
```

## 3) 원격 LLM 사용 정책
- clip 단계에서는 원격 LLM을 사용하지 않는다.
- 전제:
  - `allow_remote_llm_extract=False` (기본)
  - `compose_clips_from_refs=True`
  - `disable_remote_llm_after_refs=True` (기본)
- 주의:
  - synopsis/story 파일이 없으면 1~2단계에서 텍스트 LLM이 호출될 수 있다.
  - character/place가 pending이면 레퍼런스 생성 단계에서 이미지 API 호출이 발생할 수 있다.

## 4) 내부 합성 절차
1. scene별 `characters`, `places`, `text`를 읽어 참조 경로를 수집한다.
2. 캐릭터는 `cutout_path`(투명 PNG) 우선, 없으면 원본 이미지 경로를 사용한다.
3. 장소는 scene의 place 이미지를 우선 사용한다.
4. place 참조가 비면 프로젝트 place 이미지를 fallback 배경으로 사용한다.
5. 합성은 `yadam/gen/placeholder.py::compose_clip_from_reference_images`에서 처리한다.
6. 결과는 `work/<story-id>/clips/<NNN>.jpg`로 저장하고 `project.json` image 메타를 갱신한다.

## 5) 현재 구도 규칙
- 단일 화자(scene 1인): 상반신 중심으로 크게 배치, 좌/우 힌트 반영.
- 다인 장면(scene 2인 이상): 과대 확대 방지를 위해 인물 높이 상한 적용.
- 전신 합성은 기본 금지(상반신 위주)로 유지.
- 인물 하단이 공중에 뜨는 느낌이 나지 않도록 카드/바닥 연결형 배치 사용.

## 6) 주요 산출물
- clip 이미지: `work/<story-id>/clips/*.jpg`
- 상태 메타: `work/<story-id>/out/project.json`의 `scenes[].image`
- 감사 리포트: `work/<story-id>/out/clip_character_audit.json`

## 7) 자주 발생하는 문제와 대응
- 증상: 단색 화면/배경만 출력
  - 원인: 참조 이미지(`references`)가 비어 있음.
  - 대응: scene `characters`/`places`를 ID(`char_001`, `place_001`)로 보정 후 재생성.
- 증상: 인물이 과대 확대(예: 화면 상하 과점유)
  - 대응: 다인 장면 인물 높이 상한으로 재생성.
- 증상: 인물 하단 절단으로 유령처럼 보임
  - 대응: 하단 연결형 배치 규칙 적용 후 재생성.

## 8) 전수 재생성 절차
1. `project.json`의 모든 `scenes[].image.status`를 `pending`으로 초기화
2. `work/<story-id>/clips/*.jpg` 삭제
3. 표준 실행 명령으로 전체 재생성
4. `clip_character_audit.json` 확인

## 9) 특정 scene만 재생성 절차
1. 해당 scene의 `scenes[idx].image.status`를 `pending`으로 변경
2. 해당 clip 파일 삭제
3. 표준 실행 명령 재실행(나머지는 skip, 대상만 gen)

## 10) 운영 체크리스트
- scene `characters`/`places`가 이름이 아닌 **ID**인지 확인
- `compose_clips_from_refs=True`인지 확인
- `allow_remote_llm_extract=False` 로그 확인
- 이상 장면은 scene 단위 pending 재생성으로 빠르게 수정
