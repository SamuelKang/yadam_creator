# yadam/nlp/entity_extract.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


# 호칭/직함 기반 후보(야담/시니어 공통 확장 가능)
CHAR_HINTS = [
    "도령", "사또", "마님", "나리", "스님", "무당", "할멈", "아씨", "부인", "대감",
    "아버지", "어머니", "할아버지", "할머니", "아들", "딸", "며느리",
    "누렁이", "황소",
    # 대본 실명 폴백 보강(LLM 추출 실패 시)
    "돌쇠", "연화", "최 서리",
]

GENERIC_ROLE_HINTS = {
    "아버지", "어머니", "할아버지", "할머니", "아들", "딸", "며느리",
}

PLACE_HINTS = [
    "한양", "마을", "산", "계곡", "절", "사찰", "관아", "시장", "집", "방", "마당",
    "아파트", "병원", "요양원", "지하철", "버스", "공원",
]

# “윤 씨 부인” 같은 패턴(단순 버전)
RE_SSI = re.compile(r"([가-힣]{1,4})\s*씨\s*(부인|마님)")
RE_NAME = re.compile(r"\b([가-힣]{2,4})\b")
RE_NAME_PARTICLE = re.compile(
    r"(?<![가-힣])([가-힣]{2,4}(?:씨|이)?)\s*(?:은|는|이|가|을|를|와|과|의|께|에게|에게서|에게로)\b"
)
RE_ROLE_NAME = re.compile(r"(?:노인|노파|이장|며느리|장수|상인|사내|여인)\s+([가-힣]{2,4}(?:씨|이)?)")

NAME_STOPWORDS = {
    "조선", "영조", "영남", "지방", "마을", "산", "절", "관아", "시장", "집", "방", "마당",
    "논바닥", "바람", "하늘", "소문", "구휼미", "곳곳", "사람", "사람들", "이웃", "시대", "비극",
    "아침", "저녁", "한낮", "새벽", "그날", "며칠", "전국", "이름", "소리", "침묵",
    "흙먼지", "나뭇가지", "주름", "눈빛", "초가집", "곡간", "창호지", "마루", "부엌", "아궁이",
    "그녀", "그들", "그는", "그녀는", "얼굴", "고개", "가슴", "어르신", "장정들", "에게",
    "작대기", "괭이",
    "노인",
}


@dataclass
class Character:
    char_id: str
    name: str
    aliases: List[str]
    hints: List[str]


@dataclass
class Place:
    place_id: str
    name: str
    hints: List[str]


def extract_characters(text: str) -> List[Character]:
    found: Dict[str, Set[str]] = {}
    explicit_name_hits: Dict[str, int] = {}
    role_name_hits: Dict[str, int] = {}

    def _norm_name(raw: str) -> str:
        n = (raw or "").strip()
        for suf in ("에게서", "에게로", "에게", "에서", "으로", "로", "께서", "께", "의", "은", "는", "이", "가", "을", "를", "와", "과", "도", "만"):
            if n.endswith(suf) and len(n) - len(suf) >= 2:
                n = n[: -len(suf)]
                break
        if n.endswith("씨") and len(n) >= 3:
            # "최씨" 같은 성씨 호칭은 유지하고, 일반 "홍길동씨" 형태만 정리
            if len(n) > 3:
                n = n[:-1]
        return n

    def _valid_name(nm: str) -> bool:
        n = _norm_name(nm)
        if len(n) < 2 or len(n) > 4:
            return False
        if n in NAME_STOPWORDS:
            return False
        if n in PLACE_HINTS:
            return False
        if n in GENERIC_ROLE_HINTS:
            return False
        return True

    # NOTE:
    # 조사 결합형 일반 명사 오탐이 많아 이름 추출은 역할+이름 패턴을 우선 사용한다.

    # 역할+이름 결합형(예: 노인 판수, 이장 최씨)
    for m in RE_ROLE_NAME.finditer(text):
        n = _norm_name(m.group(1))
        if _valid_name(n):
            explicit_name_hits[n] = explicit_name_hits.get(n, 0) + 2
            role_name_hits[n] = role_name_hits.get(n, 0) + 1

    for m in RE_SSI.finditer(text):
        nm = f"{m.group(1)} 씨 {m.group(2)}"
        found.setdefault(nm, set()).add(m.group(2))

    # 실명이 1회 이상 나오면 우선 캐릭터 후보로 등록
    explicit_names = [
        n
        for n, cnt in sorted(explicit_name_hits.items(), key=lambda x: (-x[1], x[0]))
        if (cnt >= 3) or (role_name_hits.get(n, 0) >= 1)
    ]
    for n in explicit_names:
        found.setdefault(n, set()).add("name")

    # 호칭 기반
    for h in CHAR_HINTS:
        # 실명이 잡힌 경우 가족 호칭(아버지/며느리 등)은 캐릭터 canonical로 쓰지 않음
        if explicit_names and h in GENERIC_ROLE_HINTS:
            continue
        if h in text:
            found.setdefault(h, set()).add("hint")

    # 결과 정리
    chars: List[Character] = []
    i = 1
    for nm, hs in found.items():
        cid = f"char_{i:03d}"
        chars.append(Character(char_id=cid, name=nm, aliases=[], hints=sorted(hs)))
        i += 1
    return chars


def extract_places(text: str) -> List[Place]:
    found: Dict[str, Set[str]] = {}
    for h in PLACE_HINTS:
        if h in text:
            found.setdefault(h, set()).add("hint")

    places: List[Place] = []
    i = 1
    for nm, hs in found.items():
        pid = f"place_{i:03d}"
        places.append(Place(place_id=pid, name=nm, hints=sorted(hs)))
        i += 1
    return places
