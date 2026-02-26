# yadam/nlp/entity_extract.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


# 호칭/직함 기반 후보(야담/시니어 공통 확장 가능)
CHAR_HINTS = [
    "도령", "사또", "마님", "나리", "스님", "무당", "할멈", "아씨", "부인", "대감",
    "아버지", "어머니", "할아버지", "할머니", "아들", "딸", "며느리",
]

PLACE_HINTS = [
    "한양", "마을", "산", "계곡", "절", "사찰", "관아", "시장", "집", "방", "마당",
    "아파트", "병원", "요양원", "지하철", "버스", "공원",
]

# “윤 씨 부인” 같은 패턴(단순 버전)
RE_SSI = re.compile(r"([가-힣]{1,4})\s*씨\s*(부인|마님)")
RE_NAME = re.compile(r"\b([가-힣]{2,4})\b")


@dataclass
class Character:
    char_id: str
    name: str
    hints: List[str]


@dataclass
class Place:
    place_id: str
    name: str
    hints: List[str]


def extract_characters(text: str) -> List[Character]:
    found: Dict[str, Set[str]] = {}

    for m in RE_SSI.finditer(text):
        nm = f"{m.group(1)} 씨 {m.group(2)}"
        found.setdefault(nm, set()).add(m.group(2))

    # 호칭 기반
    for h in CHAR_HINTS:
        if h in text:
            found.setdefault(h, set()).add("hint")

    # 결과 정리
    chars: List[Character] = []
    i = 1
    for nm, hs in found.items():
        cid = f"char_{i:03d}"
        chars.append(Character(char_id=cid, name=nm, hints=sorted(hs)))
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