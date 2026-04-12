# 브라우저 Gemini 수동 생성: 예시 전용 가이드 (story16)

이 문서는 `story16`을 실제로 처리한 **예시 절차**만 담는다.  
다른 스토리에는 `story16`만 해당 `story-id`로 바꿔서 같은 순서로 적용한다.

## 0) 기준 파일

- 프로젝트 파일: `work/story16/out/project.json`
- 캐릭터 폴더: `work/story16/characters/`
- 장소 폴더: `work/story16/places/`
- 클립 폴더: `work/story16/clips/`

## 1) 시작 전 백업 (예시)

```bash
cp work/story16/out/project.json work/story16/out/project.json.bak_manual_$(date +%Y%m%d_%H%M%S)
```

## 2) 브라우저에서 이미지 생성 (예시)

1. Gemini 웹에서 이미지 생성 모드 진입
2. 프리셋: Nano Banana 2 선택
3. `project.json`의 프롬프트를 그대로 붙여넣기
4. 결과 다운로드 후 아래 이름으로 저장

파일명 예시:
- 캐릭터: `char_001_심_씨.jpg`
- 장소: `place_003_절.jpg`
- 클립: `015.jpg`, `161.jpg`

## 3) 수동 교체 후 project.json 반영 (예시)

아래는 클립 `015.jpg`를 수동 교체했을 때 예시다.

```json
{
  "id": 15,
  "image": {
    "path": "/Users/remnant/Projects/make_vrew/yadam_pipeline/work/story16/clips/015.jpg",
    "status": "ok",
    "last_error": null
  }
}
```

## 4) 빠른 검증 (예시)

```bash
python - <<'PY'
import json, pathlib
p='work/story16/out/project.json'
o=json.load(open(p))
missing=[]
for s in o.get('scenes',[]):
    pp=str((s.get('image') or {}).get('path') or '')
    if pp and not pathlib.Path(pp).exists():
        missing.append((s.get('id'), pp))
print('missing scene images:', len(missing))
for m in missing[:20]:
    print(m)
PY
```

```bash
ls work/story16/clips/*.jpg | wc -l
```

## 5) 실제 작업 예시 컷

아래 번호는 2인 이상 장면에서 화자 확대 확인용으로 재생성했던 실제 예시다.

- `015`
- `034`
- `042`
- `076`
- `081`
- `161`

## 6) 다른 story에 적용할 때

- `story16` → `storyNN`으로 문자열만 바꾼다.
- 폴더 구조/파일명 규칙은 동일하게 유지한다.
