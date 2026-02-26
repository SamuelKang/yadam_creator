# yadam-pipeline

야담/사연 대본(.txt)을 입력으로 받아:
- 문장 분리 및 장면(3~5문장) 분할
- 등장인물/장소 후보 추출 및 장면별 태깅
- (외부 이미지 생성 API 연동 시) 장면 이미지 생성 + 에러 placeholder 생성
- 결과 JSON 및 vrew payload(임시) 산출

## 설치
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
