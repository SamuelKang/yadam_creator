# yadam/nlp/chapter_split.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


_CHAPTER_RE = re.compile(r"^\s*Chapter\s*(\d+)\s*[:：\-]\s*(.+?)\s*$", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"^\s*=+\s*$")

_MARK_PREFIX = "§§CHAPTER|"
_MARK_SUFFIX = "§§"


@dataclass(frozen=True)
class ChapterInfo:
    no: int
    title: str


def preprocess_chapters(text: str) -> Tuple[str, str]:
    """
    입력 텍스트에서:
      - Chapter N: ... 라인을 '마커'로 치환 (문장 분리 단계에서 챕터 경계를 유지)
      - ==================== 같은 구분선은 제거
    반환:
      - marked_text: 챕터 마커 포함(문장 분리/장면 분할용)
      - clean_text : 챕터/구분선 제거(LLM/엔티티 추출용)
    """
    marked_lines: List[str] = []
    clean_lines: List[str] = []

    for line in text.splitlines():
        s = line.strip()

        # 구분선 제거
        if _SEPARATOR_RE.match(s or ""):
            continue

        m = _CHAPTER_RE.match(line)
        if m:
            no = int(m.group(1))
            title = m.group(2).strip()
            # 문장 분리기에 걸리도록 '마커 문장'으로 삽입
            marked_lines.append(f"{_MARK_PREFIX}{no}|{title}{_MARK_SUFFIX}")
            # clean_text에는 챕터 라인 미포함
            continue

        marked_lines.append(line)
        clean_lines.append(line)

    marked_text = "\n".join(marked_lines)
    clean_text = "\n".join(clean_lines)
    return marked_text, clean_text


def parse_chapter_marker(sentence: str) -> Optional[ChapterInfo]:
    """
    preprocess_chapters()가 삽입한 챕터 마커 문장인지 판별.
    """
    s = (sentence or "").strip()
    if not (s.startswith(_MARK_PREFIX) and s.endswith(_MARK_SUFFIX)):
        return None

    body = s[len(_MARK_PREFIX) : -len(_MARK_SUFFIX)]
    parts = body.split("|", 1)
    if len(parts) != 2:
        return None

    try:
        no = int(parts[0].strip())
    except Exception:
        return None
    title = parts[1].strip()
    if not title:
        title = f"Chapter {no}"
    return ChapterInfo(no=no, title=title)


def attach_chapters(sentences: List[str]) -> List[Tuple[str, Optional[ChapterInfo]]]:
    """
    문장 리스트를 순회하며:
      - 챕터 마커를 만나면 현재 챕터를 갱신
      - 일반 문장은 (문장, 현재챕터)로 반환
    챕터 마커 문장 자체는 결과에 포함하지 않음(= scene_text에 들어가지 않게).
    """
    out: List[Tuple[str, Optional[ChapterInfo]]] = []
    cur: Optional[ChapterInfo] = None

    for s in sentences:
        info = parse_chapter_marker(s)
        if info is not None:
            cur = info
            continue
        # 빈 문장 제거(선택)
        if not (s and s.strip()):
            continue
        out.append((s, cur))

    return out